import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

function getLuminance(r, g, b) {
  const [rs, gs, bs] = [r, g, b].map((c) => {
    c = c / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function getContrast(rgb1, rgb2) {
  const l1 = getLuminance(...rgb1);
  const l2 = getLuminance(...rgb2);
  const brightest = Math.max(l1, l2);
  const darkest = Math.min(l1, l2);
  return (brightest + 0.05) / (darkest + 0.05);
}

const PALETTE = {
  white: [255, 255, 255],
  slate50: [248, 250, 252],
  slate100: [241, 245, 249],
  slate200: [226, 232, 240],
  slate300: [203, 213, 225],
  slate400: [148, 163, 184],
  slate500: [100, 116, 139],
  slate600: [71, 85, 105],
  slate700: [51, 65, 85],
  slate800: [30, 41, 59],
  slate900: [15, 23, 42],
  slate950: [2, 6, 23],
  blue500: [59, 130, 246],
  blue600: [37, 99, 235],
  sky400: [96, 165, 250],
};

console.log('--- 1. WCAG AA / AAA Math Contrast Ratio Tests ---');

// Test 1: Root body foreground on background
const rootContrast = getContrast(PALETTE.slate900, PALETTE.slate50);
assert(rootContrast >= 4.5, `Root text contrast must be >= 4.5:1 (got ${rootContrast.toFixed(2)}:1)`);
console.log(`✓ Root foreground contrast: ${rootContrast.toFixed(2)}:1 (PASS)`);

// Test 2: Global outline on light background
const outlineLight = getContrast(PALETTE.blue600, PALETTE.slate50);
assert(outlineLight >= 3.0, `Focus outline on light bg must be >= 3:1 (got ${outlineLight.toFixed(2)}:1)`);
console.log(`✓ globals.css focus outline contrast (light): ${outlineLight.toFixed(2)}:1 (PASS)`);

// Test 3: Dark focus outline on dark background
const outlineDark = getContrast(PALETTE.sky400, PALETTE.slate900);
assert(outlineDark >= 3.0, `Focus outline on dark bg must be >= 3:1 (got ${outlineDark.toFixed(2)}:1)`);
console.log(`✓ globals.css focus outline contrast (dark): ${outlineDark.toFixed(2)}:1 (PASS)`);

// Test 4: slate300 on slate800, slate900, slate950
const contrastSlate800 = getContrast(PALETTE.slate300, PALETTE.slate800);
const contrastSlate900 = getContrast(PALETTE.slate300, PALETTE.slate900);
const contrastSlate950 = getContrast(PALETTE.slate300, PALETTE.slate950);
assert(contrastSlate800 >= 4.5, `slate300 on slate800 must be >= 4.5:1 (got ${contrastSlate800.toFixed(2)}:1)`);
assert(contrastSlate900 >= 4.5, `slate300 on slate900 must be >= 4.5:1 (got ${contrastSlate900.toFixed(2)}:1)`);
assert(contrastSlate950 >= 4.5, `slate300 on slate950 must be >= 4.5:1 (got ${contrastSlate950.toFixed(2)}:1)`);
console.log(`✓ text-slate-300 on dark surfaces: ${contrastSlate800.toFixed(2)}:1 / ${contrastSlate900.toFixed(2)}:1 / ${contrastSlate950.toFixed(2)}:1 (PASS)`);

// Test 5: slate600 and slate700 on light surfaces
const contrastSlate600White = getContrast(PALETTE.slate600, PALETTE.white);
const contrastSlate700Slate50 = getContrast(PALETTE.slate700, PALETTE.slate50);
assert(contrastSlate600White >= 4.5, `slate600 on white must be >= 4.5:1 (got ${contrastSlate600White.toFixed(2)}:1)`);
assert(contrastSlate700Slate50 >= 4.5, `slate700 on slate50 must be >= 4.5:1 (got ${contrastSlate700Slate50.toFixed(2)}:1)`);
console.log(`✓ text-slate-600/700 on light surfaces: ${contrastSlate600White.toFixed(2)}:1 / ${contrastSlate700Slate50.toFixed(2)}:1 (PASS)`);

console.log('\n--- 2. Source Code Static Audit Tests ---');

function walkDir(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  for (const file of list) {
    const full = path.join(dir, file);
    const stat = fs.statSync(full);
    if (stat.isDirectory()) {
      results = results.concat(walkDir(full));
    } else if (full.endsWith('.tsx') || full.endsWith('.ts') || full.endsWith('.css')) {
      results.push(full);
    }
  }
  return results;
}

const allSrcFiles = walkDir(path.join(projectRoot, 'src'));

// Test 6: Verify no low-contrast transparent zinc-500/10 or text-zinc-400 in lib/
for (const f of allSrcFiles) {
  if (f.endsWith('.ts') || f.endsWith('.tsx')) {
    const content = fs.readFileSync(f, 'utf8');
    assert(!content.includes('text-zinc-400'), `File ${f} must not use low-contrast text-zinc-400`);
    assert(!content.includes('text-zinc-500'), `File ${f} must not use low-contrast text-zinc-500`);
    assert(!content.includes('text-gray-400'), `File ${f} must not use low-contrast text-gray-400`);
  }
}
console.log('✓ Zero forbidden low-contrast classes (text-zinc-400, text-zinc-500, text-gray-400) found across src (PASS)');

// Test 7: Verify all SVGs have accessible attributes
let totalSvgs = 0;
for (const f of allSrcFiles) {
  if (f.endsWith('.tsx')) {
    const content = fs.readFileSync(f, 'utf8');
    const svgMatches = content.match(/<svg\b[\s\S]*?>/g) || [];
    for (const svg of svgMatches) {
      totalSvgs++;
      const isAccessible = /aria-hidden="true"|aria-label|aria-labelledby|role="img"/.test(svg);
      assert(isAccessible, `SVG in ${f} is missing accessible label or aria-hidden="true": ${svg.slice(0, 100)}`);
    }
  }
}
console.log(`✓ All ${totalSvgs} SVGs verified with accessible attributes (PASS)`);

// Test 8: Verify globals.css focus visible rules
const globalsCss = fs.readFileSync(path.join(projectRoot, 'src/app/globals.css'), 'utf8');
assert(globalsCss.includes(':focus-visible'), 'globals.css must define :focus-visible rules');
assert(globalsCss.includes('#2563eb'), 'globals.css must use high-contrast blue-600 focus outline');
assert(globalsCss.includes('#60a5fa'), 'globals.css must use high-contrast sky-400 dark focus outline');
console.log('✓ globals.css focus-visible high-contrast outline definitions verified (PASS)');

console.log('\n=========================================');
console.log('ALL WCAG COLOR CONTRAST & ACCESSIBILITY TESTS PASSED!');
console.log('=========================================');
