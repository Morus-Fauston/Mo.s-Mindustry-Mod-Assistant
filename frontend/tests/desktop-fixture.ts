import { test as base, expect, chromium, type Page } from '@playwright/test';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtemp, writeFile, mkdir, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';

interface NativeView { zoomFactor: number; deviceDpi: number; monitorScalePercent: number; clientWidth: number; clientHeight: number }
interface DesktopHostFixture { page: Page; temporary: string; projectPath: string; pid: number; nativeView: NativeView }

export const test = base.extend<{ desktopHost: DesktopHostFixture; nativeZoom: number }>({
  nativeZoom: [1, { option: true }],
  desktopHost: async ({ nativeZoom }, use, testInfo) => {
    const root = resolve(import.meta.dirname, '../..');
    const temporary = await mkdtemp(join(tmpdir(), 'moma-workspace-'));
    const projectPath = join(temporary, '中文 空格工程');
    await mkdir(join(projectPath, 'content/units'), { recursive: true });
    await mkdir(join(projectPath, 'content/blocks'), { recursive: true });
    await mkdir(join(projectPath, 'content/weapons'), { recursive: true });
    await mkdir(join(projectPath, 'sprites/units'), { recursive: true });
    await writeFile(join(projectPath, 'mod.json'), JSON.stringify({ name: 'native-test', displayName: '真实验收工程' }));
    await writeFile(join(projectPath, 'content/units/twin.json'), JSON.stringify({ type: 'flying', name: '同名单元', health: 137, description: '临时验收样本，来自真实磁盘\n'.repeat(40) }));
    await writeFile(join(projectPath, 'content/blocks/twin.json'), JSON.stringify({ type: 'Wall', name: '同名方块', health: 823 }));
    await writeFile(join(projectPath, 'content/weapons/laser.json'), JSON.stringify({ type: 'Weapon', name: '激光武器', reload: 31 }));
    await writeFile(join(projectPath, 'content/units/broken.json'), '{invalid');
    await writeFile(join(projectPath, 'sprites/units/twin.png'), Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'));
    await mkdir(join(temporary, 'config'));
    await writeFile(join(temporary, 'config/settings.json'), JSON.stringify({ display_name_mode: 'zh' }));
    await writeFile(join(temporary, 'config/editor_state.json'), JSON.stringify({ last_project: projectPath }));
    const server = createServer();
    await new Promise<void>(done => server.listen(0, '127.0.0.1', done));
    const address = server.address();
    if (!address || typeof address === 'string') throw new Error('测试端口分配失败');
    const port = address.port;
    await new Promise<void>(done => server.close(() => done()));
    const stop = join(temporary, 'stop');
    let output = '';
    let spawnError: Error | undefined;
    const child = spawn(resolve(root, '.venv-web/Scripts/python.exe'),
      [resolve(root, 'frontend/tests/host.py'), String(port), stop], { cwd: root, windowsHide: true,
        env: { ...process.env, MOMA_TEST_PAGE_ZOOM: String(nativeZoom) } });
    child.on('error', error => { spawnError = error; });
    child.stdout?.on('data', data => { output += data; });
    child.stderr?.on('data', data => { output += data; });
    let browser: Awaited<ReturnType<typeof chromium.connectOverCDP>> | undefined;
    try {
      await expect.poll(async () => {
        if (spawnError) throw spawnError;
        if (child.exitCode !== null) throw new Error(`宿主提前退出：${output}`);
        return fetch(`http://127.0.0.1:${port}/json/version`).then(r => r.ok).catch(() => false);
      }, { timeout: 30_000 }).toBe(true);
      browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
      const context = browser.contexts()[0];
      await expect.poll(() => context.pages().length).toBeGreaterThan(0);
      const page = context.pages()[0];
      await expect(page.locator('[data-startup="ready"]')).toBeVisible();
      const nativePid = Number(output.match(/MOMA_HOST_PID=(\d+)/)?.[1]);
      expect(nativePid).toBeGreaterThan(0);
      await expect.poll(() => output.includes('MOMA_NATIVE_VIEW=')).toBe(true);
      const nativeView = JSON.parse(output.match(/MOMA_NATIVE_VIEW=(\{[^\r\n]+\})/)![1]) as NativeView;
      expect(nativeView.zoomFactor).toBe(nativeZoom);
      await expect.poll(() => page.evaluate(() => devicePixelRatio)).toBeCloseTo(nativeView.monitorScalePercent / 100 * nativeZoom, 2);
      await testInfo.attach('原生尺寸与缩放', { body: JSON.stringify(nativeView), contentType: 'application/json' });
      await use({ page, temporary, projectPath, pid: nativePid, nativeView });
    } finally {
      await browser?.close();
      await writeFile(stop, 'stop');
      if (child.exitCode === null) await new Promise<void>(done => {
        const timer = setTimeout(() => { child.kill(); done(); }, 10_000);
        child.once('exit', () => { clearTimeout(timer); done(); });
      });
      await testInfo.attach('宿主日志', { body: output, contentType: 'text/plain' });
      const nativeLog = await readFile(join(temporary, 'config/desktop.log'), 'utf8').catch(() => '');
      await testInfo.attach('原生日志', { body: nativeLog, contentType: 'text/plain' });
      await rm(temporary, { recursive: true, force: true });
    }
  },
});

export { expect };
