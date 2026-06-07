import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {extname, join, normalize} from 'node:path';
import {spawn} from 'node:child_process';

const root = process.cwd();
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const mime = {
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
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

  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => resolve(server));
  });
}

function dumpDom(url) {
  return new Promise((resolve, reject) => {
    const child = spawn(chrome, [
      '--headless',
      '--disable-gpu',
      '--virtual-time-budget=5000',
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

function parseQa(dom) {
  const match = dom.match(/<script id="figure-qa-output" type="application\/json">([\s\S]*?)<\/script>/);
  if (!match) throw new Error('No QA output script found');
  return JSON.parse(match[1]);
}

function summarizeText(rows) {
  return rows.map(row => ({
    id: row.id,
    widthDelta: row.delta.width,
    heightDelta: row.delta.height,
    xDelta: row.delta.x,
    yDelta: row.delta.y
  }));
}

const cases = [
  ['simple-scaleX', '/tmp/font-qa/scale-fit.json'],
  ['simple-textLength', '/tmp/font-qa/textlength-fit.json'],
  ['actual-panel-C-text', '/tmp/font-qa/reference-01-place-code-opto-C-text.json']
];

const server = await serve();
const {port} = server.address();

try {
  for (const [name, spec] of cases) {
    const url = `http://127.0.0.1:${port}/skills/make-figure/assets/hybrid-renderer-template.html?spec=${encodeURIComponent(spec)}&qaDom=1&fontQa=1`;
    const qa = parseQa(await dumpDom(url));
    console.log(`\n## ${name}`);
    console.table(summarizeText(qa.textQa.rows));
    console.table((qa.fontQa.candidates || []).slice(0, 5).map(row => ({
      fontFamily: row.candidate,
      score: row.score
    })));
  }
} finally {
  server.close();
}
