/* Playwright harness for test60.html.
   Serves the calculator repo over HTTP and answers every collector URL from a local
   directory of published shards, so the page runs exactly as on GitHub Pages but offline.
   Usage as a module:
     const {withPage} = require('./harness');
     await withPage({publicDir, tab:'cases'}, async (page) => {...});
   CLI: node harness.js [--public DIR] [--dump]  -> prints the key figures of every tab as JSON.
*/
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const http = require('http'); const fs = require('fs'); const path = require('path');
const REPO = '/home/user/WarEra-Selling-Price-Calc';
const DEFAULT_PUBLIC = '/tmp/claude-0/-home-user/d4b26fab-cdf4-573a-8269-c661bf06e643/scratchpad/public';
const DATA_BASE = 'https://leblinski.github.io/-warera-case1-collector/';

function serveRepo() {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const p = decodeURIComponent(req.url.split('?')[0]);
      const f = path.join(REPO, p === '/' ? '/test60.html' : p);
      if (!f.startsWith(REPO) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); res.end(); return; }
      const ext = path.extname(f);
      res.writeHead(200, { 'Content-Type': ext === '.html' ? 'text/html; charset=utf-8' : ext === '.json' ? 'application/json' : ext === '.png' ? 'image/png' : 'application/octet-stream' });
      fs.createReadStream(f).pipe(res);
    });
    srv.listen(0, '127.0.0.1', () => resolve(srv));
  });
}

async function withPage(opts, fn) {
  opts = opts || {};
  const publicDir = opts.publicDir || DEFAULT_PUBLIC;
  const overrides = opts.overrides || {};   // {'index.json': object|string|{status:404}} -> replaces a served file
  const srv = await serveRepo();
  const port = srv.address().port;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: opts.viewport || { width: 1280, height: 900 } });
  if (opts.localStorage) {
    await ctx.addInitScript((kv) => { for (const k in kv) localStorage.setItem(k, kv[k]); }, opts.localStorage);
  }
  if (opts.now) {
    // Freeze Date.now so freshness logic is deterministic (page compares to generated_at).
    await ctx.addInitScript((t) => { const real = Date; const fixed = t; Date.now = () => fixed; }, opts.now);
  }
  const page = await ctx.newPage();
  const log = [];
  page.on('console', (m) => log.push({ type: m.type(), text: m.text() }));
  page.on('pageerror', (e) => log.push({ type: 'pageerror', text: String(e) }));
  const requests = [];
  await page.route('**/*', async (route) => {
    const url = route.request().url();
    if (url.startsWith(DATA_BASE)) {
      const rel = url.slice(DATA_BASE.length).split('?')[0];
      requests.push(rel);
      const ov = overrides[rel];
      if (ov !== undefined) {
        if (ov && typeof ov === 'object' && ov.__status) return route.fulfill({ status: ov.__status, body: ov.__body || '' });
        return route.fulfill({ status: 200, contentType: 'application/json', body: typeof ov === 'string' ? ov : JSON.stringify(ov) });
      }
      const f = path.join(publicDir, rel);
      if (fs.existsSync(f)) return route.fulfill({ status: 200, contentType: 'application/json', body: fs.readFileSync(f, 'utf8') });
      return route.fulfill({ status: 404, body: 'not found' });
    }
    if (url.startsWith('http://127.0.0.1:' + port)) return route.continue();
    // Every other host is unreachable in this environment; fail fast like the proxy does.
    requests.push('BLOCKED ' + url.split('?')[0]);
    return route.fulfill({ status: 403, body: 'blocked' });
  });
  await page.goto('http://127.0.0.1:' + port + '/test60.html');
  try {
    if (opts.tab) await page.click('#tabBar [data-tab="' + opts.tab + '"]');
    return await fn(page, { log, requests, ctx });
  } finally {
    await browser.close(); srv.close();
  }
}

const text = async (page, sel) => { const el = await page.$(sel); return el ? (await el.innerText()).replace(/\s+/g, ' ').trim() : null; };

async function dumpAll(page) {
  await page.waitForFunction(() => { const v = document.getElementById('caseVerdict'); return v && v.textContent.trim() !== '—' && v.textContent.trim() !== '—'; }, null, { timeout: 15000 }).catch(() => {});
  const out = {};
  out.dataStamp = await text(page, '#dataStamp');
  await page.click('#tabBar [data-tab="cases"]');
  out.cases = { verdict: await text(page, '#caseVerdict'), detail: await text(page, '#caseDetail'), rows: await text(page, '#caseRows'), swing: await text(page, '#caseSwing'), foot: await text(page, '#caseFoot'), books: await text(page, '#caseBooks'), tab: await text(page, '#tabCaseVal') };
  await page.click('#tabBar [data-tab="craft"]');
  out.craft = { verdict: await text(page, '#craftVerdict'), detail: await text(page, '#craftDetail'), rows: await text(page, '#craftRows'), foot: await text(page, '#craftFoot'), note: await text(page, '#craftNote'), scrap: await page.inputValue('#craftScrap'), steel: await page.inputValue('#craftSteel') };
  await page.click('#tabBar [data-tab="sort"]');
  out.sort = { detail: await text(page, '#sortDetail'), gate: await text(page, '#sortGateNote'), foot: await text(page, '#sortFoot'), rows: await text(page, '#sortRows') };
  return out;
}

module.exports = { withPage, text, dumpAll, DEFAULT_PUBLIC };

if (require.main === module) {
  const args = process.argv.slice(2); let publicDir = DEFAULT_PUBLIC;
  for (let i = 0; i < args.length; i++) if (args[i] === '--public') publicDir = args[++i];
  withPage({ publicDir }, async (page, extra) => {
    const out = await dumpAll(page);
    out._requests = extra.requests; out._console = extra.log;
    console.log(JSON.stringify(out, null, 1));
  }).catch((e) => { console.error('HARNESS FAIL', e); process.exit(1); });
}
