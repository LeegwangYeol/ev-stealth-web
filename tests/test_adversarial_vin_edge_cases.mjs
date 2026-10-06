/**
 * tests/test_adversarial_vin_edge_cases.mjs
 * Empirical stress harness for Recall Portal VIN decoding and Model Matching.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Read getRecallData.ts and inject 'with { type: "json" }' into memory for testing
let sourcePath = path.resolve(__dirname, '../src/lib/getRecallData.ts');
let jsonImport = "import rawRecallData from '../src/data/ev_recall_database.json' with { type: 'json' };";
if (!fs.existsSync(sourcePath)) {
  sourcePath = path.resolve(__dirname, '../ev-stealth-web/src/lib/getRecallData.ts');
  jsonImport = "import rawRecallData from '../ev-stealth-web/src/data/ev_recall_database.json' with { type: 'json' };";
}
const originalSource = fs.readFileSync(sourcePath, 'utf-8');
const patchedSource = originalSource.replace(
  /import rawRecallData from ['"].*?ev_recall_database\.json['"](?: with \{ type: ['"]json['"] \})?;/,
  jsonImport
);

// Write to a temporary TypeScript test fixture inside tests/ (not modifying src/!)
const testFixturePath = path.resolve(__dirname, 'temp_getRecallData_test_fixture.ts');
fs.writeFileSync(testFixturePath, patchedSource, 'utf-8');

let recallModule;
try {
  recallModule = await import('./temp_getRecallData_test_fixture.ts');
} finally {
  // Clean up fixture
  if (fs.existsSync(testFixturePath)) {
    fs.unlinkSync(testFixturePath);
  }
}

const {
  validateVinString,
  decodeVinAndCheckRecalls,
  checkRecallsByModel,
  isModelMatchForCampaign,
  isYearMatchForCampaign,
  getRecallDatabase
} = recallModule;

const db = getRecallDatabase();
console.log(`[VIN HARNESS] Database loaded: ${db.recalls.length} recalls, ${db.vin_prefixes.length} prefixes, ${db.battery_profiles.length} battery profiles.`);

const suiteResults = {
  totalTests: 0,
  passed: 0,
  failed: 0,
  findings: []
};

function assert(condition, message, metadata = {}) {
  suiteResults.totalTests++;
  if (condition) {
    suiteResults.passed++;
  } else {
    suiteResults.failed++;
    suiteResults.findings.push({ message, metadata });
    console.error(`[FAIL] ${message}`, metadata);
  }
}

// ---------------------------------------------------------
// 1. BOUNDARY & MALFORMED VIN STRINGS
// ---------------------------------------------------------
console.log('[TEST GROUP 1] Testing boundary lengths and malformed characters...');

// A. Empty and whitespace
const emptyRes = validateVinString('');
assert(!emptyRes.valid, 'Empty string should be invalid', emptyRes);
assert(emptyRes.error.includes('17자리'), 'Empty string error message specifies 17 chars');

const whitespaceRes = validateVinString('    \t\n   ');
assert(!whitespaceRes.valid, 'Whitespace-only string should be invalid', whitespaceRes);

// B. Boundary lengths (<17 and >17)
const lengths = [1, 5, 10, 15, 16, 18, 19, 32, 100, 1000];
for (const len of lengths) {
  const dummy = 'A'.repeat(len);
  const res = validateVinString(dummy);
  assert(!res.valid, `Length ${len} should be invalid`, { len, res });
  assert(res.error.includes(`${len}자리`), `Length ${len} should be reflected in error message`, { len, res });
}

// C. Disallowed letters (I, O, Q) per ISO 3779
const illegalChars = ['I', 'O', 'Q', 'i', 'o', 'q'];
for (const ch of illegalChars) {
  const vinWithIllegal = `KM8K${ch}81C8PA000000`;
  const res = validateVinString(vinWithIllegal);
  assert(!res.valid, `VIN with illegal letter '${ch}' should be rejected`, { vinWithIllegal, res });
  assert(res.error.includes('I(아이), O(오), Q(큐)'), 'Error message warns about ISO 3779 I, O, Q', { ch, res });
}

// D. Non-alphanumeric & injection vectors
const hostileVectors = [
  'KM8KR81C8PA00000!',
  'KM8KR81C8PA00000@',
  'KM8KR81C8PA00000#',
  '<script>alert(1)</script>',
  "'; DROP TABLE recalls;--",
  'KM8KR81C8PA0000\x00\x01',
  'KM8KR81C8PA0000\n\r',
  'KM8KR81C8PA한글000',
  'KM8KR81C8PA0000😊'
];

for (const vec of hostileVectors) {
  const res = validateVinString(vec);
  assert(!res.valid, `Hostile vector '${vec}' should be rejected`, { vec, res });
}

// E. Normalization (spaces and hyphens stripping, lowercase conversion)
const messyValidVin = '  km8kr81c-8pa123456  ';
const normRes = validateVinString(messyValidVin);
assert(normRes.valid, 'Messy formatted valid VIN should be normalized and valid', normRes);
assert(normRes.normalized === 'KM8KR81C8PA123456', 'Normalized VIN should be uppercase without spaces/hyphens');

// ---------------------------------------------------------
// 2. VIN DECODER & RECALL CORRELATION
// ---------------------------------------------------------
console.log('[TEST GROUP 2] Testing decodeVinAndCheckRecalls under edge cases...');

// A. Invalid VIN handling inside decodeVinAndCheckRecalls
const invalidDecode = decodeVinAndCheckRecalls('SHORT');
assert(!invalidDecode.valid, 'decodeVinAndCheckRecalls should flag invalid input', invalidDecode);
assert(invalidDecode.recalls.length === 0, 'No recalls on invalid VIN');
assert(invalidDecode.overallRiskGrade === 'SAFE', 'Safe fallback on invalid VIN');

// B. Valid 17-char VIN with Unknown WMI & Unknown Year
const unknownVin = 'ZZZ9999999Z999999';
const unknownDecode = decodeVinAndCheckRecalls(unknownVin);
assert(unknownDecode.valid, 'Valid format should pass validation even if unknown brand', unknownDecode);
assert(unknownDecode.decodedBrand === '기타/미확인 브랜드', 'Fallback brand assigned for unknown WMI', unknownDecode);
assert(unknownDecode.decodedYear === undefined, 'Unmapped year letter should yield undefined decodedYear', unknownDecode);
assert(unknownDecode.overallRiskGrade === 'SAFE', 'Overall risk safe for unknown vehicle with no matches');

// C. Test all 14 official prefix sample VINs in database
for (const p of db.vin_prefixes) {
  const dec = decodeVinAndCheckRecalls(p.sample_full_vin);
  assert(dec.valid, `Official sample ${p.sample_full_vin} must be valid`, dec);
  assert(dec.decodedBrand === p.brand, `Brand for ${p.sample_full_vin} must be ${p.brand}`, { expected: p.brand, actual: dec.decodedBrand });
  assert(dec.decodedModel === p.model_name, `Model for ${p.sample_full_vin} must be ${p.model_name}`, { expected: p.model_name, actual: dec.decodedModel });
  assert(typeof dec.overallRiskGrade === 'string', 'Overall risk grade defined');
  assert(dec.batteryProfile !== undefined || p.brand === '포르쉐', `Battery profile mapped for ${p.model_name}`);
}

// C.1 Targeted verification for Tesla Model 3 (LRW3E7EK prefix) battery profile
const m3Dec = decodeVinAndCheckRecalls('LRW3E7EK8NC123456');
assert(m3Dec.valid, 'Tesla Model 3 sample VIN must be valid', m3Dec);
assert(m3Dec.decodedBrand === '테슬라', 'Tesla Model 3 brand should be 테슬라');
assert(m3Dec.decodedModel === '모델 3', 'Tesla Model 3 model should be 모델 3');
assert(m3Dec.batteryProfile !== undefined, 'Tesla Model 3 battery profile must be mapped');
assert(m3Dec.batteryProfile.cell_supplier.includes('CATL'), 'Tesla Model 3 supplier should include CATL');
assert(m3Dec.batteryProfile.cell_chemistry.includes('LFP'), 'Tesla Model 3 chemistry should include LFP');
assert(m3Dec.batteryProfile.recommended_soc_limit === 100, 'Tesla Model 3 LFP recommended SoC limit should be 100');
assert(m3Dec.batteryProfile.fire_incident_status === 'VERIFIED_SAFE', 'Tesla Model 3 fire incident status verified safe');
assert(m3Dec.batteryProfile.underground_parking_advisory.length > 20, 'Tesla Model 3 advisory text present');

// D. Test WMI-only fallback (valid 17-char VIN with recognized WMI but unmapped model prefix)
const wmiOnlyVin = '5YJ3E1EB8MF000000'; // 5YJ is Tesla, but 5YJ3 is not in vin_prefixes (only 5YJYGDE is)
const wmiDec = decodeVinAndCheckRecalls(wmiOnlyVin);
assert(wmiDec.valid, 'WMI fallback VIN should be valid 17-char VIN', wmiDec);
assert(wmiDec.decodedBrand === '테슬라', 'WMI fallback correctly identifies 테슬라', wmiDec);
assert(wmiDec.decodedModel === undefined, 'Unmapped prefix leaves decodedModel undefined', wmiDec);
assert(wmiDec.overallRiskGrade !== undefined, 'Risk grade still calculated cleanly');

// ---------------------------------------------------------
// 3. MODEL COLLISION & DISAMBIGUATION LOGIC
// ---------------------------------------------------------
console.log('[TEST GROUP 3] Testing model matching collision protections...');

// Positive matches
assert(isModelMatchForCampaign('아이오닉 5', '아이오닉 5, 아이오닉 6'), '아이오닉 5 should match campaign with multiple models');
assert(isModelMatchForCampaign('모델 Y', '모델 3, 모델 Y'), '모델 Y should match campaign');
assert(isModelMatchForCampaign('EV6', 'EV6 (CV)'), 'EV6 should match EV6 (CV)');

// Collision protection: Numbered models must not collide
assert(!isModelMatchForCampaign('아이오닉 5', '아이오닉 6'), 'Collision guard: 아이오닉 5 MUST NOT match 아이오닉 6');
assert(!isModelMatchForCampaign('EV6', 'EV9'), 'Collision guard: EV6 MUST NOT match EV9');
assert(!isModelMatchForCampaign('EV3', 'EV6'), 'Collision guard: EV3 MUST NOT match EV6');
assert(!isModelMatchForCampaign('모델 3', '모델 Y'), 'Collision guard: 모델 3 MUST NOT match 모델 Y');
assert(!isModelMatchForCampaign('모델 S', '모델 X'), 'Collision guard: 모델 S MUST NOT match 모델 X');

// Collision protection: Old EV vs Numbered EV
assert(!isModelMatchForCampaign('아이오닉 5', '아이오닉 EV, 코나 EV'), '아이오닉 5 MUST NOT match 아이오닉 EV');
assert(!isModelMatchForCampaign('아이오닉 EV', '아이오닉 5, 아이오닉 6'), '아이오닉 EV MUST NOT match 아이오닉 5');

// ---------------------------------------------------------
// 4. YEAR MATCHING RANGE TESTS
// ---------------------------------------------------------
console.log('[TEST GROUP 4] Testing year range matching...');
assert(isYearMatchForCampaign(2022, '2021~2023'), '2022 should match 2021~2023');
assert(isYearMatchForCampaign(2021, '2021~2023'), 'Boundary start 2021 should match 2021~2023');
assert(isYearMatchForCampaign(2023, '2021~2023'), 'Boundary end 2023 should match 2021~2023');
assert(!isYearMatchForCampaign(2024, '2021~2023'), '2024 MUST NOT match 2021~2023');
assert(!isYearMatchForCampaign(2020, '2021~2023'), '2020 MUST NOT match 2021~2023');
assert(isYearMatchForCampaign(2023, '2023'), 'Single year 2023 match');
assert(!isYearMatchForCampaign(2024, '2023'), 'Single year mismatch');

// ---------------------------------------------------------
// 5. HIGH-THROUGHPUT RANDOMIZED FUZZING (10,000 iterations)
// ---------------------------------------------------------
console.log('[TEST GROUP 5] High throughput random string fuzzing (10,000 cases)...');
const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+\0\n';
let unhandledThrows = 0;

for (let i = 0; i < 10000; i++) {
  // Generate random length between 0 and 25
  const len = Math.floor(Math.random() * 26);
  let str = '';
  for (let j = 0; j < len; j++) {
    str += chars.charAt(Math.floor(Math.random() * chars.length));
  }

  try {
    const res = decodeVinAndCheckRecalls(str);
    if (res.valid) {
      // If marked valid, it must strictly be 17 chars and not contain I, O, Q
      if (res.query.length !== 17 || /[IOQ]/i.test(res.query)) {
        suiteResults.failed++;
        suiteResults.findings.push({ message: 'False positive validity on fuzzed string', str });
      }
    }
  } catch (err) {
    unhandledThrows++;
    console.error(`Crash on fuzzed input "${str}":`, err);
  }
}
assert(unhandledThrows === 0, `10,000 random inputs survived with 0 crashes (throws: ${unhandledThrows})`);

console.log('\n======================================================');
console.log(`[VIN HARNESS FINISHED] Total tests: ${suiteResults.totalTests}`);
console.log(`Passed: ${suiteResults.passed}, Failed: ${suiteResults.failed}`);
console.log(`Findings count: ${suiteResults.findings.length}`);
console.log('======================================================');

if (suiteResults.failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
