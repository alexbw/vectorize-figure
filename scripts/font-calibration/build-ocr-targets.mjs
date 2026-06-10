import {execFileSync} from 'node:child_process';
import {mkdir, writeFile} from 'node:fs/promises';
import {basename} from 'node:path';

const panels = [
  'reference-01-place-code-opto-A',
  'reference-01-place-code-opto-B',
  'reference-01-place-code-opto-C',
  'reference-01-place-code-opto-F',
  'reference-02-decision-dynamics-A',
  'reference-02-decision-dynamics-B'
];

const outDir = 'tmp/font-qa/ocr-targets';

function parseTsv(tsv) {
  const rows = tsv.trim().split(/\r?\n/);
  const header = rows.shift().split('\t');
  return rows.map(line => {
    const cols = line.split('\t');
    return Object.fromEntries(header.map((key, index) => [key, cols[index] ?? '']));
  });
}

function normalize(text) {
  return text.replace(/[|_—=~]+/g, ' ').replace(/\s+/g, ' ').trim();
}

function mergeLine(words) {
  const good = words
    .map(word => ({...word, text: normalize(word.text || ''), conf: Number(word.conf)}))
    .filter(word => word.text && word.conf > 35);
  if (!good.length) return null;
  const text = good.map(word => word.text).join(' ');
  if (text.length < 2) return null;
  if (!/[A-Za-z]/.test(text)) return null;

  const left = Math.min(...good.map(word => Number(word.left)));
  const top = Math.min(...good.map(word => Number(word.top)));
  const right = Math.max(...good.map(word => Number(word.left) + Number(word.width)));
  const bottom = Math.max(...good.map(word => Number(word.top) + Number(word.height)));
  return {
    text,
    box: {x: left, y: top, width: right - left, height: bottom - top},
    confidence: +(good.reduce((sum, word) => sum + word.conf, 0) / good.length).toFixed(1)
  };
}

function colorFor(text) {
  return /light|opto|archt|532/i.test(text) ? '#009da3' : '#111111';
}

function itemFromLine(line, index) {
  const bold = index < 2 || /timeline|trajectory|place cells|responses/i.test(line.text);
  const anchor = line.box.width < 180 && !/^[A-Z]$/.test(line.text) ? 'middle' : 'start';
  return {
    id: `ocr-${String(index + 1).padStart(2, '0')}`,
    type: 'text',
    text: line.text,
    x: anchor === 'middle' ? line.box.x + line.box.width / 2 : line.box.x,
    y: line.box.y + line.box.height,
    fontFamily: 'Helvetica, Arial, sans-serif',
    fontSize: Math.max(8, Math.min(28, line.box.height * 0.9)),
    fontWeight: bold ? 700 : 400,
    anchor,
    fill: colorFor(line.text),
    sourceBox: line.box,
    targetWidth: line.box.width,
    fit: 'scaleX',
    fitTolerancePx: 0.5,
    ocrConfidence: line.confidence
  };
}

await mkdir(outDir, {recursive: true});

for (const id of panels) {
  const image = `assets/reference/${id}-reference.png`;
  const tsv = execFileSync('tesseract', [image, 'stdout', '--psm', '6', 'tsv'], {encoding: 'utf8'});
  const rows = parseTsv(tsv);
  const lineGroups = new Map();
  for (const row of rows) {
    if (row.level !== '5') continue;
    const key = [row.block_num, row.par_num, row.line_num].join(':');
    if (!lineGroups.has(key)) lineGroups.set(key, []);
    lineGroups.get(key).push(row);
  }

  const lines = Array.from(lineGroups.values())
    .map(mergeLine)
    .filter(Boolean)
    .filter(line => line.box.width >= 10 && line.box.height >= 8)
    .filter(line => !/^[a-z]$/.test(line.text))
    .slice(0, 18);

  const geometry = execFileSync('sips', ['-g', 'pixelWidth', '-g', 'pixelHeight', image], {encoding: 'utf8'});
  const width = Number(geometry.match(/pixelWidth: (\d+)/)?.[1]);
  const height = Number(geometry.match(/pixelHeight: (\d+)/)?.[1]);

  const spec = {
    schema: 'scientific_figure_reconstruction.v1',
    id: `${id}-ocr-text-targets`,
    source: {
      path: `/assets/reference/${basename(image)}`,
      usage: 'QA-only OCR text target extraction for typography calibration.'
    },
    canvas: {width, height, background: '#ffffff'},
    typography: {
      fontFamily: 'Helvetica, Arial, sans-serif',
      defaultSize: 13,
      color: '#111111'
    },
    panels: [
      {
        id: 'ocr-text-targets',
        marks: lines.map(itemFromLine)
      }
    ],
    confidence: [
      {
        target: 'ocr-text-targets',
        confidence: 'medium',
        note: 'Generated from Tesseract line OCR; noisy lines should be ignored in visual QA.'
      }
    ]
  };

  await writeFile(`${outDir}/${id}.json`, JSON.stringify(spec, null, 2));
  console.log(`${id}: ${lines.length} OCR text targets`);
}
