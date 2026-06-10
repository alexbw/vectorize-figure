import {readFile, writeFile} from 'node:fs/promises';

const [targetPath, calibratedPath] = process.argv.slice(2);

if (!targetPath || !calibratedPath) {
  console.error('Usage: node scripts/font-calibration/apply-text-calibration.mjs output-panel.json calibrated-text-spec.json');
  process.exit(2);
}

function collectTextItems(spec) {
  const items = [];
  for (const panel of spec.panels || []) {
    for (const item of [panel.label, panel.title, ...(panel.marks || [])]) {
      if (item && item.id && item.text) items.push(item);
    }
  }
  return items;
}

function pickCalibration(item) {
  const fields = [
    'fontFamily',
    'fontSize',
    'fontWeight',
    'lineHeight',
    'targetWidth',
    'fit',
    'minScale',
    'maxScale',
    'overlayX',
    'overlayY',
    'sourceBox',
    'calibrationScore'
  ];
  return Object.fromEntries(fields
    .filter(field => item[field] !== undefined)
    .map(field => [field, item[field]]));
}

const target = JSON.parse(await readFile(targetPath, 'utf8'));
const calibrated = JSON.parse(await readFile(calibratedPath, 'utf8'));
const calibration = Object.fromEntries(collectTextItems(calibrated).map(item => [item.id, pickCalibration(item)]));

for (const panel of target.panels || []) {
  panel.textCalibration = {
    ...(panel.textCalibration || {}),
    ...calibration
  };
}

await writeFile(targetPath, `${JSON.stringify(target, null, 2)}\n`);
console.log(`Applied ${Object.keys(calibration).length} text calibration entries to ${targetPath}`);
