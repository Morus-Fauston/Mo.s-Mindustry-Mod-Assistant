import { test, expect, chromium } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import { createServer } from 'node:net';
import { resolve } from 'node:path';

test('目录包独立启动并读取随包元数据', async ({}, testInfo) => {
  const root = resolve(import.meta.dirname, '../..');
  const server = createServer();
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('测试端口分配失败');
  const port = address.port;
  await new Promise<void>(done => server.close(() => done()));
  // WebView2's official runtime variable is set only for this test process.
  const child = spawn(resolve(root, 'dist/MoMA-Web/MoMA-Web.exe'), [], {
    cwd: resolve(root, 'dist/MoMA-Web'), windowsHide: true,
    env: { ...process.env, PATH: `${process.env.SystemRoot}\\System32`,
      PYTHONPATH: '', PYTHONHOME: '',
      WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${port}` },
  });
  let output = '';
  let failure: Error | undefined;
  child.on('error', error => { failure = error; });
  child.stderr?.on('data', chunk => { output += chunk.toString(); });
  let browser: Awaited<ReturnType<typeof chromium.connectOverCDP>> | undefined;
  try {
    await expect.poll(async () => {
      if (failure) throw failure;
      if (child.exitCode !== null) throw new Error(`目录包退出：${output}`);
      return fetch(`http://127.0.0.1:${port}/json/version`).then(r => r.ok).catch(() => false);
    }, { timeout: 30_000 }).toBe(true);
    browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
    const context = browser.contexts()[0];
    await expect.poll(() => context.pages().length).toBeGreaterThan(0);
    const page = context.pages()[0];
    await expect(page.locator('[data-startup="ready"]')).toBeVisible();
    await expect(page.getByRole('heading', { name: '已加载的游戏资料' })).toBeVisible();
    await expect(page.locator('dl')).toContainText('159');
    await page.screenshot({ path: testInfo.outputPath('目录包.png') });
    await testInfo.attach('目录包启动', { body: JSON.stringify({ executable: child.spawnfile,
      pid: child.pid, url: page.url(), path: 'System32 only', text: await page.locator('dl').innerText() }, null, 2), contentType: 'application/json' });
  } finally {
    await browser?.close();
    if (child.pid && child.exitCode === null) {
      spawnSync(resolve(root, '.venv-web/Scripts/python.exe'), [resolve(root, 'frontend/tests/close_window.py'), String(child.pid)], { windowsHide: true });
      await new Promise<void>(done => {
        const timer = setTimeout(() => { child.kill(); done(); }, 10_000);
        child.once('exit', () => { clearTimeout(timer); done(); });
      });
    }
    await testInfo.attach('目录包日志', { body: output, contentType: 'text/plain' });
  }
});
