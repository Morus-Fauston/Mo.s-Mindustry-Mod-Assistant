import { test, expect, chromium } from '@playwright/test';
import { spawn, type ChildProcess } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtemp, writeFile, rm, cp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';

for (const missingMetadata of [false, true]) {
test(missingMetadata ? '真实宿主元数据缺失后修复重试' : '真实 WebView2 桌面读取离线资料并隔离静态根', async ({}, testInfo) => {
  const root = resolve(import.meta.dirname, '../..');
  const temporary = await mkdtemp(join(tmpdir(), 'moma-host-'));
  const stop = join(temporary, 'stop');
  const server = createServer();
  await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('测试端口分配失败');
  const port = address.port;
  await new Promise<void>(done => server.close(() => done()));
  let output = '';
  const child: ChildProcess = spawn(resolve(root, '.venv-web/Scripts/python.exe'),
    [resolve(root, 'frontend/tests/host.py'), String(port), stop, ...(missingMetadata ? ['missing-metadata'] : [])], { cwd: root, windowsHide: true });
  child.stdout?.on('data', chunk => { output += chunk.toString(); });
  child.stderr?.on('data', chunk => { output += chunk.toString(); });
  let browser: Awaited<ReturnType<typeof chromium.connectOverCDP>> | undefined;
  try {
    await expect.poll(async () => {
      if (child.exitCode !== null) throw new Error(`宿主提前退出：${output}`);
      return fetch(`http://127.0.0.1:${port}/json/version`).then(r => r.ok).catch(() => false);
    }, { timeout: 30_000 }).toBe(true);
    browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
    const context = browser.contexts()[0];
    await expect.poll(() => context.pages().length).toBeGreaterThan(0);
    const page = context.pages()[0];
    if (missingMetadata) {
      await expect(page.getByRole('alert')).toContainText('无法读取离线元数据');
      await page.screenshot({ path: testInfo.outputPath('元数据缺失.png') });
      await cp(resolve(root, 'metadata'), join(temporary, 'metadata'), { recursive: true });
      await page.getByRole('button', { name: '重新连接' }).click();
    }
    await expect(page.locator('[data-startup="ready"]')).toBeVisible();
    await expect(page.getByRole('heading', { name: '已加载的游戏资料' })).toBeVisible();
    const response = await page.evaluate(async () => {
      const host = window as unknown as { pywebview: { api: { bootstrap: (version: number) => Promise<any> } } };
      return { valid: await host.pywebview.api.bootstrap(1), mismatch: await host.pywebview.api.bootstrap(2),
        inputs: document.querySelectorAll('input,textarea,select').length,
        viewport: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio } };
    });
    expect(response.valid.ok).toBe(true);
    expect(response.valid.data.metadata.classCount).toBeGreaterThan(0);
    expect(response.mismatch.error.code).toBe('PROTOCOL_MISMATCH');
    expect(response.inputs).toBe(0);
    const outside = await context.request.get(new URL('/metadata/manifest.json', page.url()).href);
    expect(outside.status()).toBe(404);
    await testInfo.attach('宿主读回', { body: JSON.stringify(response, null, 2), contentType: 'application/json' });
    await page.screenshot({ path: testInfo.outputPath('真实宿主.png') });
  } finally {
    await browser?.close();
    await writeFile(stop, 'stop');
    if (child.exitCode === null) await new Promise<void>(done => {
      const timer = setTimeout(() => { child.kill(); done(); }, 10_000);
      child.once('exit', () => { clearTimeout(timer); done(); });
    });
    await testInfo.attach('宿主日志', { body: output, contentType: 'text/plain' });
    await rm(temporary, { recursive: true, force: true });
  }
});
}
