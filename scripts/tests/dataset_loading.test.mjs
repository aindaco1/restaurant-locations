import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import test from 'node:test';

const root = fileURLToPath(new URL('../../', import.meta.url));
const source = readFileSync(new URL('../../assets/js/app.js', import.meta.url), 'utf8');
const records = JSON.parse(readFileSync(new URL('../../data/violations_latest.json', import.meta.url)));
const packedResult = spawnSync('python3', ['-c',
  'import sys,json; sys.path.insert(0,"scripts"); from dataset_transport import pack_dataset; print(json.dumps(pack_dataset(json.load(open("data/violations_latest.json")))))'
], { cwd: root, encoding: 'utf8', maxBuffer: 10 * 1024 * 1024 });
assert.equal(packedResult.status, 0, packedResult.stderr);
const packed = JSON.parse(packedResult.stdout);

function createStore(fetchImpl) {
  let store;
  vm.runInNewContext(source, {
    document: {
      addEventListener: (event, callback) => callback(),
      querySelector: () => ({ content: '/preview' }),
    },
    Alpine: { store: (name, value) => { store = value; }, data: () => {} },
    fetch: fetchImpl,
    console: { warn() {}, error() {} },
  });
  return store;
}

const plain = value => JSON.parse(JSON.stringify(value));

test('browser decoder restores every archive field and grouping result', () => {
  const store = createStore();
  const decoded = store.decodeDataset(structuredClone(packed));
  assert.deepEqual(decoded, records);
  assert.deepEqual(plain(store.groupByRestaurant(decoded)), plain(store.groupByRestaurant(records)));
  assert.equal(store.decodeDataset(records), records);
});

test('browser decoder rejects corrupt observation references and unknown formats', () => {
  const store = createStore();
  for (const observation of [-1, 1, 0.5, true, '0', null]) {
    assert.throws(() => store.decodeDataset({
      format: 'observations-v1', observations: ['text'],
      records: [{ inspection: { violations: [{ observation }] } }],
    }), /Invalid observation reference/);
  }
  assert.throws(() => store.decodeDataset({ format: 'future' }), /Unsupported browser dataset format/);
});

test('loader selects the browser URL with the manifest hash and caching contract', async () => {
  const requests = [];
  const store = createStore(async (url, options) => {
    requests.push({ url, cache: options.cache });
    return { ok: true, json: async () => requests.length === 1 ? {
      datasets: { latest: {
        hash: 'testhash', url: '/data/violations_latest.json',
        browser_url: '/data/violations_browser.v1.json',
      } },
    } : structuredClone(packed) };
  });
  await store.loadViolations();
  assert.equal(store.error, null);
  assert.equal(store.loading, false);
  assert.equal(requests.length, 2);
  assert.match(requests[0].url, /^\/preview\/data\/manifest.json\?ts=/);
  assert.equal(requests[0].cache, 'no-store');
  assert.deepEqual(requests[1], {
    url: '/preview/data/violations_browser.v1.json?v=testhash', cache: 'force-cache',
  });
  assert.deepEqual(store.violations, records);
});

for (const scenario of ['old manifest', 'missing manifest']) {
  test(`loader preserves the public array fallback with ${scenario}`, async () => {
    const requests = [];
    const store = createStore(async (url) => {
      requests.push(url);
      if (requests.length === 1 && scenario === 'missing manifest') throw new Error('offline');
      return { ok: true, json: async () => requests.length === 1
        ? { datasets: { latest: { url: '/data/violations_latest.json', hash: 'oldhash' } } }
        : structuredClone(records) };
    });
    await store.loadViolations();
    assert.equal(store.error, null);
    assert.match(requests[1], /^\/preview\/data\/violations_latest.json\?v=/);
    assert.deepEqual(store.violations, records);
  });
}
