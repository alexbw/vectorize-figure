import {createServer} from 'node:http';
import {readFile, writeFile} from 'node:fs/promises';
import {extname, join, normalize} from 'node:path';
import {spawn} from 'node:child_process';

const root = process.cwd();
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const mime = {
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png'
};

function serve() {
  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://127.0.0.1');
      const rel = normalize(decodeURIComponent(url.pathname)).replace(/^(\.\.[/\\])+/, '').replace(/^[/\\]/, '');
      const file = join(root, rel || 'README.md');
      const data = await readFile(file);
      res.writeHead(200, {'content-type': mime[extname(file)] || 'application/octet-stream'});
      res.end(data);
    } catch (error) {
      res.writeHead(404, {'content-type': 'text/plain'});
      res.end(String(error.message || error));
    }
  });
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(server)));
}

function dumpDom(url) {
  return new Promise((resolve, reject) => {
    const child = spawn(chrome, [
      '--headless',
      '--disable-gpu',
      '--virtual-time-budget=30000',
      '--dump-dom',
      url
    ]);
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', chunk => { stdout += chunk; });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.on('exit', code => {
      if (code === 0) resolve(stdout);
      else reject(new Error(stderr || `Chrome exited ${code}`));
    });
  });
}

function parseOutput(dom) {
  const match = dom.match(/<script id="calibration-output" type="application\/json">([\s\S]*?)<\/script>/);
  if (!match) throw new Error('No calibration output found');
  return JSON.parse(match[1]);
}

const specPath = process.argv[2];
const outputPrefix = process.argv[3];

if (!specPath || !outputPrefix) {
  console.error('Usage: node scripts/font-calibration/run-calibration.mjs /path/to/spec.json output/prefix');
  console.error('Example: node scripts/font-calibration/run-calibration.mjs /tmp/font-qa/reference-01-place-code-opto-C-text.json tmp/font-qa/reference-01-place-code-opto-C');
  process.exit(2);
}

const server = await serve();
try {
  const {port} = server.address();
  const calibrationPage = '/scripts/font-calibration/calibrate.html';
  const normalizedSpecPath = specPath.startsWith('/') ? specPath : `/${specPath}`;
  const url = `http://127.0.0.1:${port}${calibrationPage}?spec=${encodeURIComponent(normalizedSpecPath)}`;
  const output = parseOutput(await dumpDom(url));
  await writeFile(`${outputPrefix}-calibrated.json`, JSON.stringify(output.spec, null, 2));
  await writeFile(`${outputPrefix}-calibration-report.json`, JSON.stringify(output.calibration, null, 2));
  console.table(output.calibration.map(row => ({
    id: row.id,
    family: row.family,
    size: row.size,
    weight: row.weight,
    scaleX: row.scaleX,
    score: row.score,
    baselineScore: row.baselineScore,
    improvement: row.improvement
  })));
} finally {
  server.close();
}
