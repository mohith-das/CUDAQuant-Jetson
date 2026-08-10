const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const base = 'http://100.109.22.68:8000';
  const routes = ['/', '/strategies', '/data', '/execution', '/experiments', '/models', '/scheduler', '/llm', '/regimes', '/system', '/models/compare'];
  for (const r of routes) {
    await page.goto(base + r, { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(2000);
    const name = r === '/' ? 'dashboard' : r.replace(/\//g, '_').replace(/^_/, '');
    await page.screenshot({ path: `/tmp/ui_${name}.png`, fullPage: false });
    console.log(`Screenshot: ${name}`);
  }
  await browser.close();
})();
