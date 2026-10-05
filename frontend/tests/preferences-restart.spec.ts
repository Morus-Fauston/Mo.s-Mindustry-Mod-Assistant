import { test, expect, chromium, type Browser, type Page, type TestInfo } from '@playwright/test';
import { spawn, execFileSync, type ChildProcess } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '../..');
const contentPath = 'content/units/restart-unit.json';
interface Host {
  child: ChildProcess;
  stop: string;
  port: number;
  log: string;
  spawnError?: Error;
  browser?: Browser;
  page?: Page;
  pid?: number;
}

async function uniquePort(used: Set<number>) {
  for (let attempt = 0; attempt < 10; attempt++) {
    const server = createServer();
    await new Promise<void>((done, reject) => {
      server.once('error', reject);
      server.listen(0, '127.0.0.1', done);
    });
    const address = server.address();
    await new Promise<void>((done, reject) => server.close(error => error ? reject(error) : done()));
    if (address && typeof address !== 'string' && !used.has(address.port)) {
      used.add(address.port);
      return address.port;
    }
  }
  throw new Error('无法为重启宿主分配独立端口');
}

async function launch(temporary: string, hosts: Host[], ports: Set<number>) {
  const port = await uniquePort(ports), stop = join(temporary, `stop-${hosts.length + 1}`);
  const child = spawn(join(root, '.venv-web/Scripts/python.exe'),
    [join(root, 'frontend/tests/host.py'), String(port), stop],
    { cwd: root, windowsHide: true, env: { ...process.env, MOMA_TEST_PAGE_ZOOM: '1' } });
  const host: Host = { child, stop, port, log: '' };
  hosts.push(host);
  child.on('error', error => { host.spawnError = error; });
  child.stdout?.on('data', data => { host.log += data.toString(); });
  child.stderr?.on('data', data => { host.log += data.toString(); });
  await expect.poll(async () => {
    if (host.spawnError) throw host.spawnError;
    if (child.exitCode !== null || child.signalCode !== null) throw new Error(`宿主提前退出：${host.log}`);
    return fetch(`http://127.0.0.1:${port}/json/version`).then(response => response.ok).catch(() => false);
  }, { timeout: 30_000 }).toBe(true);
  host.browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
  const context = host.browser.contexts()[0];
  await expect.poll(() => context.pages().length).toBeGreaterThan(0);
  host.page = context.pages()[0];
  await expect(host.page.locator('[data-startup="ready"]')).toBeVisible();
  await host.page.evaluate(() => {
    const host = window as any, request = host.pywebview.api.request;
    host.restartRequests = [];
    host.pywebview.api.request = async (envelope: any) => {
      const record = { action: envelope.action, started: performance.now(), finished: 0 };
      host.restartRequests.push(record);
      try { return await request(envelope); }
      finally { record.finished = performance.now(); }
    };
    document.addEventListener('click', event => {
      const node = (event.target as Element).closest('[data-path]');
      if (node) host.restartRequests.push({ click: node.getAttribute('data-path'), at: performance.now() });
    }, true);
  });
  await expect.poll(() => host.log.includes('MOMA_NATIVE_VIEW=')).toBe(true);
  host.pid = Number(host.log.match(/MOMA_HOST_PID=(\d+)/)?.[1]);
  expect(host.pid).toBeGreaterThan(0);
  // Windows venv python.exe can launch the actual interpreter as a child.
  // Verify ownership before targeting its native window, not PID equality.
  if (host.pid !== child.pid) {
    const parent = execFileSync('powershell.exe', ['-NoProfile', '-Command',
      `(Get-CimInstance Win32_Process -Filter 'ProcessId = ${host.pid}').ParentProcessId`],
    { windowsHide: true, timeout: 10_000, encoding: 'utf8' });
    expect(Number(parent.trim())).toBe(child.pid);
  }
  return host as Host & { page: Page; pid: number };
}

async function normalClose(host: Host & { pid: number }) {
  // Target only this newly spawned native window. WM_CLOSE exercises the real
  // close guard, the frontend flush and close_window before process teardown.
  execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    join(root, 'frontend/tests/window-close.ps1'), '-TestProcessId', String(host.pid)],
  { windowsHide: true, timeout: 10_000 });
  await expect.poll(() => host.child.exitCode, { timeout: 15_000 }).toBe(0);
  expect(host.child.signalCode).toBeNull();
  await host.browser?.close().catch(() => {});
  host.browser = undefined;
}

async function cleanup(host: Host, info: TestInfo, index: number) {
  if (host.page && !host.page.isClosed()) {
    const requests = await host.page.evaluate(() => (window as any).restartRequests).catch(() => []);
    await info.attach(`重启宿主${index + 1}调用时序`, { body: JSON.stringify(requests), contentType: 'application/json' });
  }
  try {
    if (host.child.exitCode === null && host.child.signalCode === null && !host.spawnError) {
      await writeFile(host.stop, 'stop');
      try {
        await expect.poll(() => host.child.exitCode !== null || host.child.signalCode !== null,
          { timeout: 12_000 }).toBe(true);
      } catch {
        host.child.kill();
        await expect.poll(() => host.child.exitCode !== null || host.child.signalCode !== null,
          { timeout: 5_000 }).toBe(true);
      }
    }
  } finally {
    await host.browser?.close().catch(() => {});
    await info.attach(`重启宿主${index + 1}日志`, { body: host.log, contentType: 'text/plain' });
  }
}

async function openRecent(page: Page, project: string) {
  await page.getByRole('button').filter({ hasText: project }).click();
  await expect(page.getByRole('button', { name: '文件面板', exact: true })).toBeVisible();
}

async function openUnit(page: Page) {
  const tree = page.getByRole('tree', { name: '工程文件', exact: true });
  await expect(tree).toBeVisible();
  for (let level = 0; level < 12 && await tree.locator('[aria-expanded="false"]').count(); level++) {
    await tree.locator('[aria-expanded="false"]').first().click();
  }
  await tree.locator(`[data-path="${contentPath}"]`).click();
  const form = page.getByRole('tabpanel', { name: contentPath, exact: true });
  await expect(form.locator('[data-field="health"] input[type="text"]')).toHaveValue('137');
  await expect(page.locator('[data-preview-status]')).toHaveAttribute('data-preview-status', 'ready');
  return form;
}

test('两个独立 WebView2 进程通过真实界面保存并恢复设置布局与最近工程', async ({}, info) => {
  test.setTimeout(120_000);
  const temporary = await mkdtemp(join(tmpdir(), 'moma-preferences-restart-'));
  const config = join(temporary, 'config'), project = join(temporary, '重启 中文工程');
  const hosts: Host[] = [], ports = new Set<number>();
  try {
    await mkdir(config);
    await mkdir(join(project, 'content/units'), { recursive: true });
    await mkdir(join(project, 'sprites/units'), { recursive: true });
    await writeFile(join(project, 'mod.json'), JSON.stringify({ name: 'restart-test', displayName: '重启持久化工程' }));
    await writeFile(join(project, contentPath), JSON.stringify({ type: 'flying', name: '重启样本', health: 137 }));
    await writeFile(join(project, 'sprites/units/restart-unit.png'), Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'));
    // No settings override: the first launch must read the real shipped defaults.
    await writeFile(join(config, 'editor_state.json'), JSON.stringify({ last_project: project, retained: '保留未知键' }));
    const first = await launch(temporary, hosts, ports);
    await openRecent(first.page, project);
    const initialForm = await openUnit(first.page);
    await expect(initialForm.getByRole('textbox', { name: '生命值 (health)', exact: true })).toHaveValue('137');
    await first.page.getByRole('button', { name: '设置', exact: true }).click();
    const dialog = first.page.getByRole('dialog', { name: '设置', exact: true });
    await expect(dialog.getByRole('combobox', { name: '字段显示名', exact: true })).toHaveValue('zh_en');
    await dialog.getByRole('combobox', { name: '主题', exact: true }).selectOption('dark');
    await dialog.getByRole('combobox', { name: '字段显示名', exact: true }).selectOption('en');
    await dialog.getByRole('textbox', { name: '预览倍率', exact: true }).fill('6');
    await dialog.getByRole('textbox', { name: '自动保存间隔', exact: true }).fill('0');
    await dialog.getByRole('button', { name: '应用', exact: true }).click();
    await expect(dialog.getByRole('button', { name: '应用', exact: true })).toBeDisabled();
    await expect(dialog.getByRole('button', { name: '关闭', exact: true })).toBeEnabled();
    await dialog.getByRole('button', { name: '关闭', exact: true }).click();
    await expect(first.page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await expect(initialForm.getByRole('textbox', { name: 'health', exact: true })).toHaveValue('137');
    await expect(first.page.locator('canvas[aria-label^="贴图预览；"]')).toHaveAttribute('data-scale', '6');

    const left = first.page.getByRole('separator', { name: '文件面板宽度', exact: true });
    await expect(left).toHaveAttribute('aria-disabled', 'false');
    const originalWidth = Number(await left.getAttribute('aria-valuenow'));
    await left.focus(); await left.press('ArrowRight');
    const diskLayout = async () => JSON.parse(await readFile(join(config, 'editor_state.json'), 'utf8')).web_workbench;
    await expect.poll(async () => (await diskLayout())?.leftWidth).toBeGreaterThan(originalWidth);
    const width = (await diskLayout()).leftWidth as number;
    await first.page.getByRole('button', { name: '文件面板', exact: true }).click();
    await expect(first.page.locator('[data-layout-panel="files"]')).toBeHidden();
    await expect.poll(async () => (await diskLayout()).filesVisible).toBe(false);
    await first.page.screenshot({ path: info.outputPath('首次保存偏好.png') });
    await normalClose(first);

    const second = await launch(temporary, hosts, ports);
    expect(second.pid).not.toBe(first.pid);
    expect(second.port).not.toBe(first.port);
    expect(second.stop).not.toBe(first.stop);
    await expect(second.page.locator('html')).toHaveAttribute('data-theme', 'dark');
    await openRecent(second.page, project);
    const files = second.page.getByRole('button', { name: '文件面板', exact: true });
    await expect(files).toHaveAttribute('aria-pressed', 'false');
    await expect(second.page.locator('[data-layout-panel="files"]')).toBeHidden();
    await second.page.getByRole('button', { name: '设置', exact: true }).click();
    const restoredDialog = second.page.getByRole('dialog', { name: '设置', exact: true });
    await expect(restoredDialog.getByRole('combobox', { name: '主题', exact: true })).toHaveValue('dark');
    await expect(restoredDialog.getByRole('combobox', { name: '字段显示名', exact: true })).toHaveValue('en');
    await expect(restoredDialog.getByRole('textbox', { name: '预览倍率', exact: true })).toHaveValue('6');
    await expect(restoredDialog.getByRole('textbox', { name: '自动保存间隔', exact: true })).toHaveValue('0');
    await restoredDialog.getByRole('button', { name: '关闭', exact: true }).click();
    await files.click();
    await expect(second.page.getByRole('separator', { name: '文件面板宽度', exact: true })).toHaveAttribute('aria-valuenow', String(width));
    const restoredForm = await openUnit(second.page);
    await expect(restoredForm.getByRole('textbox', { name: 'health', exact: true })).toHaveValue('137');
    await expect(second.page.locator('canvas[aria-label^="贴图预览；"]')).toHaveAttribute('data-scale', '6');
    expect(JSON.parse(await readFile(join(project, contentPath), 'utf8')).health).toBe(137);
    expect(JSON.parse(await readFile(join(config, 'editor_state.json'), 'utf8')).retained).toBe('保留未知键');
    await second.page.screenshot({ path: info.outputPath('新进程恢复偏好与真实工程.png') });
    await info.attach('独立进程重启证据', { body: JSON.stringify({
      first: { pid: first.pid, port: first.port, stop: first.stop, exitCode: first.child.exitCode },
      second: { pid: second.pid, port: second.port, stop: second.stop },
      restored: { theme: 'dark', displayMode: 'en', zoom: 6, autoSave: 0, leftWidth: width, filesInitiallyVisible: false },
      settings: JSON.parse(await readFile(join(config, 'settings.json'), 'utf8')),
      editorState: JSON.parse(await readFile(join(config, 'editor_state.json'), 'utf8')),
    }, null, 2), contentType: 'application/json' });
    await normalClose(second);
  } finally {
    const failures: unknown[] = [];
    for (const [index, host] of hosts.entries()) {
      try { await cleanup(host, info, index); } catch (error) { failures.push(error); }
    }
    await info.attach('重启原生日志', { body: await readFile(join(config, 'desktop.log'), 'utf8').catch(() => ''), contentType: 'text/plain' });
    // Keep evidence on disk if a test-owned process could not be terminated.
    if (failures.length) throw new AggregateError(failures, `宿主清理失败，保留目录：${temporary}`);
    await rm(temporary, { recursive: true, force: true });
  }
});
