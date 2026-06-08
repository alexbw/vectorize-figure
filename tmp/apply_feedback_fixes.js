const fs = require('fs');
const path = require('path');

const root = process.cwd();

function panelPath(id, ext) {
  return path.join(root, 'outputs', `${id}-vectorize-figure-batch`, `${id}.${ext}`);
}

function readJson(id) {
  return JSON.parse(fs.readFileSync(panelPath(id, 'json'), 'utf8'));
}

function writeJson(id, spec) {
  fs.writeFileSync(panelPath(id, 'json'), `${JSON.stringify(spec, null, 2)}\n`);
}

function patchFile(id, replacements) {
  const htmlPath = panelPath(id, 'html');
  let text = fs.readFileSync(htmlPath, 'utf8');
  for (const [from, to] of replacements) {
    if (!text.includes(from)) {
      throw new Error(`Missing HTML patch target in ${id}: ${from.slice(0, 80)}`);
    }
    text = text.replace(from, to);
  }
  fs.writeFileSync(htmlPath, text);
}

function update(id, updater) {
  const spec = readJson(id);
  updater(spec);
  writeJson(id, spec);
}

update('reference-02-decision-dynamics-A', spec => {
  const table = spec.panels[0].processTable;
  table.columnGap = 3;
  table.headerStrokeWidth = 1.05;
  table.accentStrokeWidth = 2.8;
});

patchFile('reference-02-decision-dynamics-A', [[
`        const x = table.x + index * table.columnWidth;
        svg.appendChild(node('rect', {
          x,
          y: table.topY,
          width: table.columnWidth,
          height: table.headerHeight,
          fill: '#f7f7f7',
          stroke: '#d0d0d0',
          'stroke-width': 0.8,
          'data-id': \`\${table.id}-\${column.id}-header\`
        }));
        svg.appendChild(node('line', {
          x1: x,
          y1: table.topY,
          x2: x + table.columnWidth,
          y2: table.topY,
          stroke: column.accent,
          'stroke-width': 2
        }));
        addText(svg, {
          text: column.header,
          x: x + table.columnWidth / 2,`,
`        const gap = table.columnGap || 0;
        const cellWidth = table.columnWidth - gap;
        const x = table.x + index * table.columnWidth + gap / 2;
        svg.appendChild(node('rect', {
          x,
          y: table.topY,
          width: cellWidth,
          height: table.headerHeight,
          fill: '#f7f7f7',
          stroke: '#d0d0d0',
          'stroke-width': table.headerStrokeWidth || 0.8,
          'data-id': \`\${table.id}-\${column.id}-header\`
        }));
        svg.appendChild(node('line', {
          x1: x,
          y1: table.topY,
          x2: x + cellWidth,
          y2: table.topY,
          stroke: column.accent,
          'stroke-width': column.accentStrokeWidth || table.accentStrokeWidth || 2
        }));
        addText(svg, {
          text: column.header,
          x: x + cellWidth / 2,`
], [
`            x: x + table.columnWidth / 2,
            y: table.topY + table.headerHeight + 27,`,
`            x: x + cellWidth / 2,
            y: table.topY + table.headerHeight + 27,`
], [
`            x: x + table.columnWidth / 2,
            y: table.topY + table.headerHeight + 84,`,
`            x: x + cellWidth / 2,
            y: table.topY + table.headerHeight + 84,`
], [
`          addRichText(svg, x + table.columnWidth / 2, table.topY + table.headerHeight + 84, column.behaviorRich, {...defaults, defaultSize: 12});`,
`          addRichText(svg, x + cellWidth / 2, table.topY + table.headerHeight + 84, column.behaviorRich, {...defaults, defaultSize: 12});`
]]);

update('reference-02-decision-dynamics-C', spec => {
  const strip = spec.panels[0].layoutObjects.find(o => o.id === 'epoch-strip');
  strip.gap = 2;
  strip.strokeWidth = 1.15;
  strip.labelYOffset = 18;
  strip.bbox.height = 25;
});

patchFile('reference-02-decision-dynamics-C', [[
`        svg.appendChild(svgEl('rect', {x: x0, y: b.y, width: x1 - x0, height: b.height, fill: segment.fill, stroke: segment.stroke}));
        addText(svg, segment.label, (x0 + x1) / 2, b.y + 18, {'font-size': 10, 'text-anchor': 'middle'});`,
`        const gap = strip.gap || 0;
        const rectX = x0 + gap / 2;
        const rectWidth = Math.max(0, (x1 - x0) - gap);
        svg.appendChild(svgEl('rect', {x: rectX, y: b.y, width: rectWidth, height: b.height, fill: segment.fill, stroke: segment.stroke, 'stroke-width': strip.strokeWidth || 1}));
        addText(svg, segment.label, (x0 + x1) / 2, b.y + (strip.labelYOffset || 18), {'font-size': 10, 'text-anchor': 'middle'});`
]]);

update('reference-02-decision-dynamics-E', spec => {
  const scale = spec.coordinateSystems.find(s => s.id === 'panel-e.percent-color');
  scale.range = ['#084ead', '#f8f8f8', '#d7191c'];
  const cells = spec.panels[0].matrix.cells;
  cells.find(c => c.id === 'actual-left-decoded-left').value = 11;
  cells.find(c => c.id === 'actual-left-decoded-left').label = '11';
  cells.find(c => c.id === 'actual-right-decoded-left').value = 89;
  cells.find(c => c.id === 'actual-right-decoded-left').label = '89';
  cells.find(c => c.id === 'actual-left-decoded-right').value = 87;
  cells.find(c => c.id === 'actual-left-decoded-right').label = '87';
  cells.find(c => c.id === 'actual-right-decoded-right').value = 13;
  cells.find(c => c.id === 'actual-right-decoded-right').label = '13';
});

update('reference-03-learning-remapping-A', spec => {
  const day3 = spec.panels[0].plotGroup.heatmaps.find(h => h.id === 'day-3');
  day3.tickLabelOffsets = {'100': {x: -6, y: 0}};
});

patchFile('reference-03-learning-remapping-A', [[
`          addText(svg, {text: tick.label, x, y: axisY + 21, fontSize: 14, anchor: 'middle'}, {fontFamily});`,
`          const offset = (hm.tickLabelOffsets && hm.tickLabelOffsets[tick.label]) || {x: 0, y: 0};
          addText(svg, {text: tick.label, x: x + offset.x, y: axisY + 21 + offset.y, fontSize: 14, anchor: 'middle'}, {fontFamily});`
]]);

update('reference-03-learning-remapping-F', spec => {
  const bar = spec.panels[0].layoutObjects.find(o => o.id === 'activity-colorbar');
  bar.tickSide = 'left';
});

patchFile('reference-03-learning-remapping-F', [[
`        svg.appendChild(svgNode('line', {x1: bar.bbox.x + bar.bbox.width, y1: y, x2: bar.bbox.x + bar.bbox.width + 5, y2: y, stroke: '#111111', 'stroke-width': 1}));
        text(svg, {text: t.label, x: bar.bbox.x - 5, y: y + 4, fontSize: 11, anchor: 'end'});`,
`        const tickLeft = bar.tickSide === 'left';
        const tickX = tickLeft ? bar.bbox.x : bar.bbox.x + bar.bbox.width;
        svg.appendChild(svgNode('line', {x1: tickX, y1: y, x2: tickX + (tickLeft ? -5 : 5), y2: y, stroke: '#111111', 'stroke-width': 1}));
        text(svg, {text: t.label, x: tickLeft ? bar.bbox.x - 7 : bar.bbox.x + bar.bbox.width + 7, y: y + 4, fontSize: 11, anchor: tickLeft ? 'end' : 'start'});`
]]);

update('reference-04-motor-manifold-A', spec => {
  const pc2 = spec.panels[0].scene.axes.find(a => a.id === 'pc2-axis');
  pc2.label.x = 333;
  pc2.label.y = 296;
  pc2.label.rotation = -28;
  const legend = spec.panels[0].legend;
  legend.center = {x: 427, y: 101};
  legend.outerRadius = 31;
  legend.innerRadius = 16;
  legend.labels = [
    {text: '0°', x: 464, y: 104, anchor: 'start'},
    {text: '90°', x: 427, y: 64, anchor: 'middle'},
    {text: '180°', x: 389, y: 104, anchor: 'end'},
    {text: '270°', x: 427, y: 144, anchor: 'middle'}
  ];
  legend.markerLegend.items = [
    {label: 'Start', x: 408, y: 170, fill: '#666666', stroke: '#111111'},
    {label: 'End', x: 408, y: 190, fill: '#ffffff', stroke: '#111111'}
  ];
});

update('reference-04-motor-manifold-B', spec => {
  const panel = spec.panels.find(p => p.id === 'condition-315');
  panel.plot.truncateXAxisAfter = 3.1;
});

patchFile('reference-04-motor-manifold-B', [[
`      g.appendChild(el('line', {x1: box.x, y1: box.y + box.height, x2: box.x + box.width, y2: box.y + box.height, stroke: styles.axisStroke, 'stroke-width': styles.axisStrokeWidth}));`,
`      const xAxisEnd = panel.plot.truncateXAxisAfter === undefined ? box.x + box.width : scales.x(panel.plot.truncateXAxisAfter);
      g.appendChild(el('line', {x1: box.x, y1: box.y + box.height, x2: xAxisEnd, y2: box.y + box.height, stroke: styles.axisStroke, 'stroke-width': styles.axisStrokeWidth}));`
], [
`        g.appendChild(el('line', {x1: x, y1: box.y + box.height, x2: x, y2: box.y + box.height + 4, stroke: styles.axisStroke, 'stroke-width': styles.tickStrokeWidth, 'data-axis': 'pc1', 'data-value': value}));
        addText(g, String(value), x, box.y + box.height + 17, {size: 16, anchor: 'middle'});`,
`        if (panel.plot.truncateXAxisAfter !== undefined && value > panel.plot.truncateXAxisAfter) continue;
        g.appendChild(el('line', {x1: x, y1: box.y + box.height, x2: x, y2: box.y + box.height + 4, stroke: styles.axisStroke, 'stroke-width': styles.tickStrokeWidth, 'data-axis': 'pc1', 'data-value': value}));
        addText(g, String(value), x, box.y + box.height + 17, {size: 16, anchor: 'middle'});`
]]);

patchFile('reference-04-motor-manifold-C', [[
`      const labelOffset = 9;
      addText(group, {text: '90°', x: plot.center.x, y: plot.center.y - plot.radius - labelOffset, fontSize: 11, anchor: 'middle', role: 'angle-label'});
      addText(group, {text: '0°', x: plot.center.x + plot.radius + labelOffset - 1, y: plot.center.y + 4, fontSize: 11, anchor: 'middle', role: 'angle-label'});
      addText(group, {text: '270°', x: plot.center.x, y: plot.center.y + plot.radius + 15, fontSize: 11, anchor: 'middle', role: 'angle-label'});
      if (plot.id === 'unit-1' || plot.id === 'unit-5') {
        addText(group, {text: '180°', x: plot.center.x - plot.radius - 10, y: plot.center.y + 4, fontSize: 11, anchor: 'middle', role: 'angle-label'});`,
`      const labelOffset = 14;
      addText(group, {text: '90°', x: plot.center.x, y: plot.center.y - plot.radius - labelOffset, fontSize: 11, anchor: 'middle', role: 'angle-label'});
      addText(group, {text: '0°', x: plot.center.x + plot.radius + labelOffset, y: plot.center.y + 4, fontSize: 11, anchor: 'start', role: 'angle-label'});
      addText(group, {text: '270°', x: plot.center.x, y: plot.center.y + plot.radius + labelOffset + 8, fontSize: 11, anchor: 'middle', role: 'angle-label'});
      if (plot.id === 'unit-1' || plot.id === 'unit-5') {
        addText(group, {text: '180°', x: plot.center.x - plot.radius - labelOffset, y: plot.center.y + 4, fontSize: 11, anchor: 'end', role: 'angle-label'});`
]]);

update('reference-04-motor-manifold-G', spec => {
  for (const annotation of spec.panels[0].annotations) {
    annotation.y2Value = 0.001;
  }
});

update('reference-05-grid-remapping-F', spec => {
  const title = spec.panels[0].annotations.find(a => a.id === 'delta-title');
  title.text = 'Gridness\n(B - A)';
});

update('reference-06-replay-stimulation-C', spec => {
  for (const mark of spec.panels[0].marks.filter(m => m.type === 'lineSeries')) {
    mark.fillUnder = mark.id === 'pre-posterior' ? '#006b6b' : '#ff5a00';
    mark.fillOpacity = 0.16;
  }
});

patchFile('reference-06-replay-stimulation-C', [[
`      svg.appendChild(make('path', {
        d,
        fill: mark.fill || 'none',
        stroke: mark.stroke,
        'stroke-width': mark.strokeWidth || 1.5,
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'data-mark-id': mark.id,
        'data-mark-type': mark.type
      }));`,
`      if (mark.fillUnder) {
        const first = mark.points[0];
        const last = mark.points[mark.points.length - 1];
        const areaD = d + \` L\${project.x(last[0]).toFixed(2)},\${project.y(0).toFixed(2)} L\${project.x(first[0]).toFixed(2)},\${project.y(0).toFixed(2)} Z\`;
        svg.appendChild(make('path', {
          d: areaD,
          fill: mark.fillUnder,
          opacity: mark.fillOpacity || 0.16,
          stroke: 'none',
          'data-mark-id': \`\${mark.id}-under-curve\`,
          'data-mark-type': 'areaFill'
        }));
      }
      svg.appendChild(make('path', {
        d,
        fill: mark.fill || 'none',
        stroke: mark.stroke,
        'stroke-width': mark.strokeWidth || 1.5,
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        'data-mark-id': mark.id,
        'data-mark-type': mark.type
      }));`
]]);

update('reference-07-cross-region-small-multiples-F', spec => {
  const panel = spec.panels[0];
  for (const group of panel.groups) {
    group.box.y += 1;
    group.box.height -= 2;
  }
  panel.plot.tickInside = true;
});

patchFile('reference-07-cross-region-small-multiples-F', [[
`      const bottomY = panel.groups[panel.groups.length - 1].box.y + panel.groups[panel.groups.length - 1].box.height;
      x.ticks.forEach((tick) => {
        const tx = xScale(tick.value, xDomain, xRange);
        svg.appendChild(svgNode('line', {
          x1: tx,
          y1: bottomY,
          x2: tx,
          y2: bottomY + 6,`,
`      const bottomY = panel.groups[panel.groups.length - 1].box.y + panel.groups[panel.groups.length - 1].box.height;
      x.ticks.forEach((tick) => {
        const tx = xScale(tick.value, xDomain, xRange);
        svg.appendChild(svgNode('line', {
          x1: tx,
          y1: panel.plot.tickInside ? bottomY - 6 : bottomY,
          x2: tx,
          y2: bottomY,`
]]);

update('reference-07-cross-region-small-multiples-H', spec => {
  const bar = spec.panels[0].layoutObjects.find(o => o.id === 'colorbar');
  bar.bbox = {x: 128, y: 283, width: 218, height: 12};
  bar.label.x = 237;
  bar.label.y = 276;
});

update('reference-08-neuropixels-central-heatmap-C', spec => {
  const panel = spec.panels[0];
  const plot = panel.plot;
  plot.dataBbox.height = 535;
  plot.axes.xAxis.line.y1 = 560;
  plot.axes.xAxis.line.y2 = 560;
  plot.axes.yAxis.line.y2 = 560;
  const strip = panel.layoutObjects.find(o => o.id === 'panel-c-color-strip');
  strip.bbox.height = 535;
  strip.segments[0].toY = 407;
  strip.segments[1].fromY = 407;
  strip.segments[1].toY = 560;
  panel.layoutObjects.push({
    id: 'panel-c-region-strip',
    type: 'segmentedColorbar',
    orientation: 'horizontal',
    bbox: {x: 84, y: 570, width: 541, height: 13},
    segments: [
      {id: 'region-a', fromX: 84, toX: 219, fill: '#009688', label: 'A'},
      {id: 'region-b', fromX: 219, toX: 354, fill: '#e0a500', label: 'B'},
      {id: 'region-c', fromX: 354, toX: 489, fill: '#009688', label: 'A'},
      {id: 'region-d', fromX: 489, toX: 625, fill: '#e0a500', label: 'B'}
    ]
  });
});

patchFile('reference-08-neuropixels-central-heatmap-C', [[
`        for (const segment of item.segments) {
          svg.appendChild(svgEl('rect', {
            x: item.bbox.x,
            y: segment.fromY,
            width: item.bbox.width,
            height: segment.toY - segment.fromY,
            fill: segment.fill,
            stroke: 'none',
            'data-layout-id': item.id,
            'data-segment-id': segment.id
          }));
        }
        svg.appendChild(svgEl('rect', {
          x: item.bbox.x,
          y: item.bbox.y,
          width: item.bbox.width,
          height: item.bbox.height,
          fill: 'none',
          stroke: '#ffffff',
          'stroke-width': 0.6
        }));`,
`        for (const segment of item.segments) {
          const horizontal = item.orientation === 'horizontal';
          svg.appendChild(svgEl('rect', {
            x: horizontal ? segment.fromX : item.bbox.x,
            y: horizontal ? item.bbox.y : segment.fromY,
            width: horizontal ? segment.toX - segment.fromX : item.bbox.width,
            height: horizontal ? item.bbox.height : segment.toY - segment.fromY,
            fill: segment.fill,
            stroke: 'none',
            'data-layout-id': item.id,
            'data-segment-id': segment.id
          }));
        }
        svg.appendChild(svgEl('rect', {
          x: item.bbox.x,
          y: item.bbox.y,
          width: item.bbox.width,
          height: item.bbox.height,
          fill: 'none',
          stroke: '#ffffff',
          'stroke-width': 0.6
        }));
        if (item.orientation === 'horizontal') {
          for (const segment of item.segments) {
            const x = (segment.fromX + segment.toX) / 2;
            appendText(svg, {text: segment.label, x, y: item.bbox.y + item.bbox.height + 11, fontSize: 10, anchor: 'middle'});
          }
        }`
], [
`          y: box.y + box.height + 18,`,
`          y: box.y + box.height + 28,`
]]);

update('reference-08-neuropixels-central-heatmap-F', spec => {
  const panel = spec.panels[0];
  const coords = spec.coordinateSystems[0].x;
  coords.positions = [130, 185, 240, 315, 385];
  panel.plot.x.categories.forEach((cat, i) => { cat.x = coords.positions[i]; });
  const values = panel.data.find(d => d.id === 'region-decoding-estimates').values;
  Object.assign(values.find(v => v.id === 'L1'), {mean: 0.46, low: 0.37, high: 0.54});
  Object.assign(values.find(v => v.id === 'L2'), {mean: 0.43, low: 0.35, high: 0.51});
  Object.assign(values.find(v => v.id === 'L3'), {mean: 0.47, low: 0.43, high: 0.52});
  Object.assign(values.find(v => v.id === 'R1'), {mean: 0.69, low: 0.61, high: 0.77});
  Object.assign(values.find(v => v.id === 'R2'), {mean: 0.48, low: 0.36, high: 0.60});
  panel.marks.find(m => m.id === 'teal-estimates').marker.stroke = '#111111';
  panel.marks.find(m => m.id === 'teal-estimates').marker.strokeWidth = 0.6;
  panel.marks.find(m => m.id === 'orange-estimates').marker.stroke = '#111111';
  panel.marks.find(m => m.id === 'orange-estimates').marker.strokeWidth = 0.6;
});

console.log('Applied targeted feedback fixes.');
