import {readFile} from 'node:fs/promises';

const reportPath = process.argv[2];
const minImproved = Number(process.argv[3] || 1);

if (!reportPath) {
  console.error('Usage: node scripts/font-calibration/assert-improvement.mjs path/to/calibration-report.json [min-improved-labels]');
  process.exit(2);
}

const report = JSON.parse(await readFile(reportPath, 'utf8'));
const rows = Array.isArray(report) ? report : [];
const improved = rows.filter(row => Number(row.improvement) > 0);

if (improved.length < minImproved) {
  console.error(`Expected at least ${minImproved} improved labels, saw ${improved.length}.`);
  console.error(JSON.stringify(rows.map(row => ({
    id: row.id,
    score: row.score,
    baselineScore: row.baselineScore,
    improvement: row.improvement
  })), null, 2));
  process.exit(1);
}

const regressions = rows.filter(row => Number(row.improvement) <= 0);
console.log(`Improved labels: ${improved.length}/${rows.length}`);
if (regressions.length) {
  console.log(`Non-improving labels kept for visual review: ${regressions.map(row => row.id).join(', ')}`);
}
