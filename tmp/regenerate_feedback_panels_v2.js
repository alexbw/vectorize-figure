const fs = require('fs');
const path = require('path');

const root = process.cwd();

function panelPath(id, ext) {
  return path.join(root, 'outputs', `${id}-make-figure-batch`, `${id}.${ext}`);
}

function readJson(id) {
  return JSON.parse(fs.readFileSync(panelPath(id, 'json'), 'utf8'));
}

function writeJson(id, spec) {
  fs.writeFileSync(panelPath(id, 'json'), `${JSON.stringify(spec, null, 2)}\n`);
}

function patchText(id, replacements) {
  const file = panelPath(id, 'html');
  let text = fs.readFileSync(file, 'utf8');
  for (const [from, to] of replacements) {
    if (!text.includes(from)) {
      throw new Error(`Missing patch target in ${id}: ${from.slice(0, 120)}`);
    }
    text = text.replace(from, to);
  }
  fs.writeFileSync(file, text);
}

function updateJson(id, fn) {
  const spec = readJson(id);
  fn(spec);
  writeJson(id, spec);
}

// 2A: regenerate the phase/process table with measured cell text behavior.
updateJson('reference-02-decision-dynamics-A', spec => {
  const table = spec.panels[0].processTable;
  table.columnGap = 4;
  table.headerFontSize = 12;
  table.cellFontSize = 10.5;
  table.richCellFontSize = 10.5;
  table.processY = 60;
  table.behaviorY = 116;
  table.headerStrokeWidth = 1;
  table.accentStrokeWidth = 2.4;
});

patchText('reference-02-decision-dynamics-A', [[
`    function addRichText(svg, x, y, runs, defaults, anchor = 'middle') {
      const text = node('text', {
        x,
        y,
        fill: '#111111',
        'font-family': defaults.fontFamily,
        'font-size': defaults.defaultSize,
        'text-anchor': anchor,
        'dominant-baseline': 'alphabetic'
      });
      let lineIndex = 0;
      runs.forEach((run, index) => {
        const parts = String(run.text).split('\\n');
        parts.forEach((part, partIndex) => {
          const tspan = node('tspan', {
            x: partIndex > 0 ? x : undefined,
            dy: partIndex > 0 ? 14 : (index === 0 ? 0 : undefined),
            fill: run.fill || '#111111'
          });
          tspan.textContent = part;
          text.appendChild(tspan);
          if (partIndex > 0) lineIndex += 1;
        });
      });
      text.dataset.lineCount = String(lineIndex + 1);
      svg.appendChild(text);
      return text;
    }`,
`    function addRichText(svg, x, y, runs, defaults, anchor = 'middle') {
      const fontSize = defaults.defaultSize || 11;
      const lineHeight = defaults.lineHeight || 1.15;
      const text = node('text', {
        x,
        y,
        fill: '#111111',
        'font-family': defaults.fontFamily,
        'font-size': fontSize,
        'text-anchor': anchor,
        'dominant-baseline': 'alphabetic'
      });
      let lineIndex = 0;
      let atLineStart = true;
      runs.forEach((run) => {
        String(run.text).split('\\n').forEach((part, partIndex) => {
          if (partIndex > 0) {
            lineIndex += 1;
            atLineStart = true;
          }
          if (part === '') return;
          const tspan = node('tspan', {
            x: atLineStart ? x : undefined,
            dy: atLineStart ? (lineIndex === 0 ? 0 : fontSize * lineHeight) : undefined,
            fill: run.fill || '#111111'
          });
          tspan.textContent = part;
          text.appendChild(tspan);
          atLineStart = false;
        });
      });
      text.dataset.lineCount = String(lineIndex + 1);
      svg.appendChild(text);
      return text;
    }`
], [
`          fontSize: 13`,
`          fontSize: table.headerFontSize || 13`
], [
`            y: table.topY + table.headerHeight + 27,
            anchor: 'middle',
            fontSize: 12`,
`            y: table.topY + (table.processY || table.headerHeight + 27),
            anchor: 'middle',
            fontSize: table.cellFontSize || 12`
], [
`            y: table.topY + table.headerHeight + 84,
            anchor: 'middle',
            fontSize: 12`,
`            y: table.topY + (table.behaviorY || table.headerHeight + 84),
            anchor: 'middle',
            fontSize: table.cellFontSize || 12`
], [
`          addRichText(svg, x + cellWidth / 2, table.topY + table.headerHeight + 84, column.behaviorRich, {...defaults, defaultSize: 12});`,
`          addRichText(svg, x + cellWidth / 2, table.topY + (table.behaviorY || table.headerHeight + 84), column.behaviorRich, {...defaults, defaultSize: table.richCellFontSize || 11, lineHeight: 1.2});`
]]);

// 3A: edge tick labels are kept inside each small-multiple tick band.
updateJson('reference-03-learning-remapping-A', spec => {
  const group = spec.panels[0].plotGroup;
  group.xAxis.edgeTickPolicy = 'inside';
  for (const hm of group.heatmaps) delete hm.tickLabelOffsets;
});

patchText('reference-03-learning-remapping-A', [[
`          const offset = (hm.tickLabelOffsets && hm.tickLabelOffsets[tick.label]) || {x: 0, y: 0};
          addText(svg, {text: tick.label, x: x + offset.x, y: axisY + 21 + offset.y, fontSize: 14, anchor: 'middle'}, {fontFamily});`,
`          let anchor = 'middle';
          let labelX = x;
          if (group.xAxis.edgeTickPolicy === 'inside' && tick.value === group.xAxis.domain[0]) {
            anchor = 'start';
            labelX = x + 2;
          } else if (group.xAxis.edgeTickPolicy === 'inside' && tick.value === group.xAxis.domain[1]) {
            anchor = 'end';
            labelX = x - 2;
          }
          addText(svg, {text: tick.label, x: labelX, y: axisY + 20, fontSize: 12, anchor}, {fontFamily});`
]]);

// 3F: source has colorbar ticks/labels on the right.
updateJson('reference-03-learning-remapping-F', spec => {
  const bar = spec.panels[0].layoutObjects.find(o => o.id === 'activity-colorbar');
  bar.tickSide = 'right';
});

// 4B: bottom-right panel keeps the visible x ticks even though the axis segment is shortened.
updateJson('reference-04-motor-manifold-B', spec => {
  const panel = spec.panels.find(p => p.id === 'condition-315');
  panel.plot.truncateXAxisAfter = 3.1;
  panel.plot.forceXTicks = true;
});

patchText('reference-04-motor-manifold-B', [[
`      const xTicks = panel.id.endsWith('180') || panel.id.endsWith('225') || panel.id.endsWith('270') ? [-6, 0, 6] : [];`,
`      const xTicks = panel.plot.forceXTicks || panel.id.endsWith('180') || panel.id.endsWith('225') || panel.id.endsWith('270') ? [-6, 0, 6] : [];`
], [
`        if (panel.plot.truncateXAxisAfter !== undefined && value > panel.plot.truncateXAxisAfter) continue;
        g.appendChild(el('line', {x1: x, y1: box.y + box.height, x2: x, y2: box.y + box.height + 4, stroke: styles.axisStroke, 'stroke-width': styles.tickStrokeWidth, 'data-axis': 'pc1', 'data-value': value}));`,
`        g.appendChild(el('line', {x1: x, y1: box.y + box.height, x2: x, y2: box.y + box.height + 4, stroke: styles.axisStroke, 'stroke-width': styles.tickStrokeWidth, 'data-axis': 'pc1', 'data-value': value}));`
]]);

// 4C: restore close but legible polar degree spacing.
patchText('reference-04-motor-manifold-C', [[
`      const labelOffset = 14;
      addText(group, {text: '90°', x: plot.center.x, y: plot.center.y - plot.radius - labelOffset, fontSize: 11, anchor: 'middle', role: 'angle-label'});
      addText(group, {text: '0°', x: plot.center.x + plot.radius + labelOffset, y: plot.center.y + 4, fontSize: 11, anchor: 'start', role: 'angle-label'});
      addText(group, {text: '270°', x: plot.center.x, y: plot.center.y + plot.radius + labelOffset + 8, fontSize: 11, anchor: 'middle', role: 'angle-label'});
      if (plot.id === 'unit-1' || plot.id === 'unit-5') {
        addText(group, {text: '180°', x: plot.center.x - plot.radius - labelOffset, y: plot.center.y + 4, fontSize: 11, anchor: 'end', role: 'angle-label'});`,
`      const labelOffset = 7;
      addText(group, {text: '90°', x: plot.center.x, y: plot.center.y - plot.radius - labelOffset, fontSize: 11, anchor: 'middle', role: 'angle-label'});
      addText(group, {text: '0°', x: plot.center.x + plot.radius + labelOffset, y: plot.center.y + 4, fontSize: 11, anchor: 'start', role: 'angle-label'});
      addText(group, {text: '270°', x: plot.center.x, y: plot.center.y + plot.radius + labelOffset + 8, fontSize: 11, anchor: 'middle', role: 'angle-label'});
      if (plot.id === 'unit-1' || plot.id === 'unit-5') {
        addText(group, {text: '180°', x: plot.center.x - plot.radius - labelOffset, y: plot.center.y + 4, fontSize: 11, anchor: 'end', role: 'angle-label'});`
]]);

// 7F: draw left/right spines for each strip and keep bottom ticks inside.
updateJson('reference-07-cross-region-small-multiples-F', spec => {
  spec.panels[0].plot.tickInside = true;
  spec.panels[0].plot.showVerticalBorders = true;
});

patchText('reference-07-cross-region-small-multiples-F', [[
`        svg.appendChild(svgNode('line', {
          x1: box.x,
          y1: box.y + box.height,
          x2: box.x + box.width,
          y2: box.y + box.height,
          stroke: '#111111',
          'stroke-width': 1,
          'shape-rendering': 'crispEdges',
          'data-object-id': \`\${group.id}-bottom-rule\`
        }));

        const events = makeRasterEvents(group, xDomain);`,
`        svg.appendChild(svgNode('line', {
          x1: box.x,
          y1: box.y + box.height,
          x2: box.x + box.width,
          y2: box.y + box.height,
          stroke: '#111111',
          'stroke-width': 1,
          'shape-rendering': 'crispEdges',
          'data-object-id': \`\${group.id}-bottom-rule\`
        }));
        if (panel.plot.showVerticalBorders) {
          svg.appendChild(svgNode('line', {
            x1: box.x,
            y1: box.y - 1,
            x2: box.x,
            y2: box.y + box.height,
            stroke: '#111111',
            'stroke-width': 1,
            'shape-rendering': 'crispEdges',
            'data-object-id': \`\${group.id}-left-rule\`
          }));
          svg.appendChild(svgNode('line', {
            x1: box.x + box.width,
            y1: box.y - 1,
            x2: box.x + box.width,
            y2: box.y + box.height,
            stroke: '#111111',
            'stroke-width': 1,
            'shape-rendering': 'crispEdges',
            'data-object-id': \`\${group.id}-right-rule\`
          }));
        }

        const events = makeRasterEvents(group, xDomain);`
]]);

// 7H: regenerate as a normal frame page so the gallery does not clip the colorbar.
function regenerate7H() {
  const id = 'reference-07-cross-region-small-multiples-H';
  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${id} reconstruction</title>
  <style>
    html, body { margin: 0; background: #eeeeee; color: #111111; font-family: Arial, Helvetica, sans-serif; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 14px; background: #ffffff; border-bottom: 1px solid #cfcfcf; }
    h1 { margin: 0; font-size: 16px; font-weight: 700; }
    .note { margin-top: 3px; font-size: 12px; color: #555555; }
    .toggle { display: inline-flex; border: 1px solid #aaaaaa; border-radius: 4px; overflow: hidden; flex: 0 0 auto; }
    .toggle button { border: 0; padding: 5px 10px; background: #ffffff; color: #111111; font: inherit; font-size: 12px; cursor: pointer; }
    .toggle button.active { background: #111111; color: #ffffff; }
    main { min-height: calc(100vh - 48px); display: grid; place-items: center; padding: 16px; box-sizing: border-box; }
    .frame { position: relative; background: #ffffff; border: 1px solid #d0d0d0; box-shadow: 0 1px 5px rgba(0,0,0,0.08); overflow: hidden; }
    .surface, .reference { position: absolute; inset: 0; }
    .reference { display: none; width: 100%; height: 100%; object-fit: contain; background: #ffffff; }
    .show-reference .surface { display: none; }
    .show-reference .reference { display: block; }
    svg { position: absolute; inset: 0; }
  </style>
</head>
<body>
  <header>
    <div><h1 id="title">${id}</h1><div class="note">Generated candidate is rendered from JSON. Source image is QA-only.</div></div>
    <div class="toggle" aria-label="View mode"><button id="generatedButton" class="active" type="button">Generated</button><button id="referenceButton" type="button">Reference</button></div>
  </header>
  <main><div id="frame" class="frame"><div id="surface" class="surface"></div><img id="reference" class="reference" alt="QA reference source image"></div></main>
  <script>
    const SVG_NS = 'http://www.w3.org/2000/svg';
    const SPEC_URL = '${id}.json';
    const $ = id => document.getElementById(id);
    function el(name, attrs = {}, parent) {
      const node = document.createElementNS(SVG_NS, name);
      for (const [key, value] of Object.entries(attrs)) if (value !== undefined && value !== null) node.setAttribute(key, value);
      if (parent) parent.appendChild(node);
      return node;
    }
    function text(parent, value, attrs = {}) {
      const node = el('text', attrs, parent);
      node.textContent = value;
      return node;
    }
    function colorAt(value, scale) {
      if (value === null || value === undefined) return scale.missingColor;
      const t = Math.max(0, Math.min(1, (value - scale.domain[0]) / (scale.domain[1] - scale.domain[0])));
      const start = [255, 255, 255], end = [11, 60, 149];
      const rgb = start.map((s, i) => Math.round(s + (end[i] - s) * t));
      return \`rgb(\${rgb[0]}, \${rgb[1]}, \${rgb[2]})\`;
    }
    function render(spec) {
      const panel = spec.panels[0];
      const grid = spec.coordinateSystems.find(item => item.id === 'heatmap-grid');
      const scale = spec.coordinateSystems.find(item => item.id === 'decoding-color');
      const frame = $('frame');
      frame.style.width = spec.canvas.width + 'px';
      frame.style.height = spec.canvas.height + 'px';
      $('reference').src = spec.source.path;
      const svg = el('svg', {width: spec.canvas.width, height: spec.canvas.height, viewBox: \`0 0 \${spec.canvas.width} \${spec.canvas.height}\`, role: 'img', 'aria-label': spec.id});
      el('rect', {x: 0, y: 0, width: spec.canvas.width, height: spec.canvas.height, fill: spec.canvas.background}, svg);
      $('surface').replaceChildren(svg);
      text(svg, panel.label.text, {x: panel.label.x, y: panel.label.y, 'font-size': panel.label.fontSize, 'font-weight': panel.label.fontWeight});
      text(svg, panel.title.text, {x: panel.title.x, y: panel.title.y, 'font-size': panel.title.fontSize, 'font-weight': panel.title.fontWeight});
      const corner = panel.layoutObjects.find(item => item.id === 'train-test-corner');
      corner.lines.forEach(line => text(svg, line.text, {x: line.x, y: line.y, 'font-size': line.fontSize}));
      const matrix = el('g', {'data-mark-type': 'heatmap'}, svg);
      panel.data.values.forEach((row, r) => row.forEach((value, c) => {
        const x = grid.bbox.x + c * grid.cellWidth;
        const y = grid.bbox.y + r * grid.cellHeight;
        el('rect', {x, y, width: grid.cellWidth, height: grid.cellHeight, fill: colorAt(value, scale), stroke: '#eef2f8', 'stroke-width': 1}, matrix);
        text(matrix, value === null ? '—' : value.toFixed(2), {x: x + grid.cellWidth / 2, y: y + grid.cellHeight / 2 + 4, 'text-anchor': 'middle', 'font-size': 10});
      }));
      const regionLabels = panel.annotations.find(item => item.id === 'region-labels');
      panel.data.rows.forEach((region, i) => text(svg, region, {x: regionLabels.rowLabelX, y: grid.bbox.y + i * grid.cellHeight + grid.cellHeight / 2 + regionLabels.rowLabelDy, 'font-size': regionLabels.fontSize, 'text-anchor': 'end', fill: regionLabels.colors[region]}));
      panel.data.columns.forEach((region, i) => text(svg, region, {x: grid.bbox.x + i * grid.cellWidth + grid.cellWidth / 2, y: regionLabels.columnLabelY, 'font-size': regionLabels.fontSize, 'text-anchor': 'middle', fill: regionLabels.colors[region]}));
      const frameObj = panel.layoutObjects.find(item => item.id === 'matrix-frame');
      el('rect', {x: frameObj.bbox.x, y: frameObj.bbox.y, width: frameObj.bbox.width, height: frameObj.bbox.height, fill: 'none', stroke: frameObj.stroke, 'stroke-width': frameObj.strokeWidth}, svg);
      const colorbar = panel.layoutObjects.find(item => item.id === 'colorbar');
      const defs = el('defs', {}, svg);
      const gradient = el('linearGradient', {id: 'decoding-color-gradient', x1: '0%', x2: '100%', y1: '0%', y2: '0%'}, defs);
      el('stop', {offset: '0%', 'stop-color': scale.range[0]}, gradient);
      el('stop', {offset: '100%', 'stop-color': scale.range[1]}, gradient);
      text(svg, colorbar.label.text, {x: colorbar.label.x, y: colorbar.label.y, 'font-size': colorbar.label.fontSize, 'text-anchor': colorbar.label.textAnchor});
      el('rect', {x: colorbar.bbox.x, y: colorbar.bbox.y, width: colorbar.bbox.width, height: colorbar.bbox.height, fill: 'url(#decoding-color-gradient)', stroke: '#111111', 'stroke-width': 0.8}, svg);
      colorbar.ticks.forEach(tick => {
        const x = colorbar.bbox.x + (tick.value - scale.domain[0]) / (scale.domain[1] - scale.domain[0]) * colorbar.bbox.width;
        el('line', {x1: x, x2: x, y1: colorbar.bbox.y + colorbar.bbox.height, y2: colorbar.bbox.y + colorbar.bbox.height + 5, stroke: '#111111', 'stroke-width': 0.8}, svg);
        text(svg, tick.label, {x, y: colorbar.bbox.y + colorbar.bbox.height + 18, 'font-size': 12, 'text-anchor': 'middle'});
      });
    }
    function setMode(reference) {
      $('frame').classList.toggle('show-reference', reference);
      $('generatedButton').classList.toggle('active', !reference);
      $('referenceButton').classList.toggle('active', reference);
    }
    $('generatedButton').addEventListener('click', () => setMode(false));
    $('referenceButton').addEventListener('click', () => setMode(true));
    fetch(SPEC_URL).then(r => r.json()).then(render).catch(error => { $('surface').textContent = error.message; });
  </script>
</body>
</html>
`;
  fs.writeFileSync(panelPath(id, 'html'), html);
}
regenerate7H();

// 8C: remove invented horizontal x-axis color strip; restore source y strip geometry.
updateJson('reference-08-neuropixels-central-heatmap-C', spec => {
  const panel = spec.panels[0];
  panel.layoutObjects = panel.layoutObjects.filter(o => o.id !== 'panel-c-region-strip');
  const plot = panel.plot;
  plot.dataBbox.height = 564;
  plot.axes.xAxis.line.y1 = 589;
  plot.axes.xAxis.line.y2 = 589;
  plot.axes.yAxis.line.y2 = 589;
  const strip = panel.layoutObjects.find(o => o.id === 'panel-c-color-strip');
  strip.bbox = {x: 69, y: 25, width: 10, height: 564};
  strip.segments = [
    {id: 'upper-teal-block', fromY: 25, toY: 432, fill: '#009688', label: 'upper sorted block'},
    {id: 'lower-gold-block', fromY: 432, toY: 589, fill: '#e0a500', label: 'lower sorted block'}
  ];
});

// 8F: restore axes from nested line objects and make y tick labels unambiguous.
patchText('reference-08-neuropixels-central-heatmap-F', [[
`      line(svg, plot.axes.xAxis);
      line(svg, plot.axes.yAxis);`,
`      line(svg, {...plot.axes.xAxis.line, id: plot.axes.xAxis.id, stroke: plot.axes.xAxis.stroke, strokeWidth: plot.axes.xAxis.strokeWidth, type: 'axis'});
      line(svg, {...plot.axes.yAxis.line, id: plot.axes.yAxis.id, stroke: plot.axes.yAxis.stroke, strokeWidth: plot.axes.yAxis.strokeWidth, type: 'axis'});`
], [
`          fontSize: 13,
          anchor: 'end'`,
`          fontSize: 14,
          anchor: 'end'`
]]);

console.log('Regenerated targeted feedback panels v2.');
