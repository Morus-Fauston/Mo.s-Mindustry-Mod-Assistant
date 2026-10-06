import { test as base, expect, chromium, type Page } from '@playwright/test';
import { execFile, spawn, type ChildProcess } from 'node:child_process';
import { promisify } from 'node:util';
import { createServer } from 'node:net';
import { mkdtemp, writeFile, mkdir, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';

interface NativeView { zoomFactor: number; deviceDpi: number; monitorScalePercent: number; clientWidth: number; clientHeight: number }
interface DesktopHostFixture { page: Page; temporary: string; projectPath: string; pid: number; nativeView: NativeView }
interface ProcessIdentity { pid: number; createdTicks: string; name: string }
const executeFile = promisify(execFile);

async function ownedProcesses(action: 'sample' | 'check' | 'terminate', known: ProcessIdentity[], timeout: number, rootProcessId?: number) {
  const args = ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
    resolve(import.meta.dirname, 'owned-processes.ps1'), '-Action', action, '-KnownJson', JSON.stringify(known)];
  if (rootProcessId) args.push('-RootProcessId', String(rootProcessId));
  const { stdout } = await executeFile('powershell.exe', args, { windowsHide: true, timeout, maxBuffer: 1024 * 1024 });
  return JSON.parse(stdout.trim()) as { identities?: ProcessIdentity[]; survivors?: ProcessIdentity[]; reused: ProcessIdentity[]; sampledUtc: string };
}

async function waitForExit(child: ChildProcess, milliseconds: number) {
  if (child.exitCode !== null || child.signalCode !== null) return true;
  return new Promise<boolean>(done => {
    const finish = () => { clearTimeout(timer); child.off('exit', exited); done(true); };
    const exited = () => finish();
    const timer = setTimeout(() => { child.off('exit', exited); done(false); }, milliseconds);
    child.once('exit', exited);
    // Covers an exit between the first check and listener registration.
    if (child.exitCode !== null || child.signalCode !== null) finish();
  });
}

async function closeConnection(browser: Awaited<ReturnType<typeof chromium.connectOverCDP>> | undefined, milliseconds: number) {
  if (!browser) return;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([browser.close(), new Promise<never>((_, reject) => {
      timeout = setTimeout(() => reject(new Error('断开CDP超过剩余预算')), milliseconds);
    })]);
  } finally { clearTimeout(timeout); }
}

export const test = base.extend<{ desktopHost: DesktopHostFixture; nativeZoom: number; hostLifetimeSeconds: number }>({
  nativeZoom: [1, { option: true }],
  hostLifetimeSeconds: [120, { option: true }],
  desktopHost: async ({ nativeZoom, hostLifetimeSeconds }, use, testInfo) => {
    const declaredDeadline = testInfo.annotations.find(value => value.type === 'moma-test-absolute-deadline')?.description;
    // Reserve final-report time for the surrounding automatic fixture.
    const absoluteDeadline = declaredDeadline === undefined ? Date.now() + hostLifetimeSeconds * 1000 : Number(declaredDeadline) - 2_000;
    if (!Number.isFinite(absoluteDeadline)) throw new Error('宿主绝对截止时间无效');
    const remaining = (maximum: number, reserve = 0) => {
      const milliseconds = absoluteDeadline - reserve - Date.now();
      if (milliseconds <= 0) throw new Error('宿主共享绝对预算耗尽；不为fixture清理重开预算');
      return Math.min(maximum, milliseconds);
    };
    const bounded = async <T>(operation: () => Promise<T>, maximum: number): Promise<T> => {
      const milliseconds = remaining(maximum);
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        return await Promise.race([operation(), new Promise<never>((_, reject) => {
          timer = setTimeout(() => reject(new Error('宿主操作超过共享剩余预算')), milliseconds);
        })]);
      } finally { clearTimeout(timer); }
    };
    const root = resolve(import.meta.dirname, '../..');
    const temporary = await mkdtemp(join(tmpdir(), 'moma-workspace-'));
    testInfo.annotations.push({ type: 'moma-test-stop-path', description: join(temporary, 'stop') });
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
        env: { ...process.env, MOMA_TEST_PAGE_ZOOM: String(nativeZoom),
          MOMA_TEST_HOST_LIFETIME_SECONDS: String(hostLifetimeSeconds) } });
    child.on('error', error => { spawnError = error; });
    child.stdout?.on('data', data => { output += data; });
    child.stderr?.on('data', data => { output += data; });
    let browser: Awaited<ReturnType<typeof chromium.connectOverCDP>> | undefined;
    const identities = new Map<string, ProcessIdentity>();
    const lifecycle: any = { spawnedPid: child.pid, absoluteDeadlineEpochMs: absoluteDeadline, samples: [], errors: [], forcedTermination: false,
      coverage: 'Creation-time identities observed at process start, host ready, and before stop; descendants born and reparented wholly between samples are not claimed covered.' };
    const remember = (values: ProcessIdentity[]) => values.forEach(value => identities.set(`${value.pid}:${value.createdTicks}`, value));
    const sample = async (rootPid?: number, reserve = 0) => {
      const result = await ownedProcesses('sample', [...identities.values()], remaining(8_000, reserve), rootPid);
      remember(result.identities ?? []); lifecycle.samples.push(result);
    };
    try {
      if (child.pid) await sample(child.pid);
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
      await sample();
      expect([...identities.values()].some(value => value.pid === nativePid), '原生宿主必须属于本次启动的进程树').toBe(true);
      await expect.poll(() => output.includes('MOMA_NATIVE_VIEW=')).toBe(true);
      const nativeView = JSON.parse(output.match(/MOMA_NATIVE_VIEW=(\{[^\r\n]+\})/)![1]) as NativeView;
      expect(nativeView.zoomFactor).toBe(nativeZoom);
      await expect.poll(() => page.evaluate(() => devicePixelRatio)).toBeCloseTo(nativeView.monitorScalePercent / 100 * nativeZoom, 2);
      await testInfo.attach('原生尺寸与缩放', { body: JSON.stringify(nativeView), contentType: 'application/json' });
      await use({ page, temporary, projectPath, pid: nativePid, nativeView });
    } finally {
      // Every cleanup action remains reachable after a CDP/sample/stop failure.
      // Preserve the final 10 seconds for identity-checked failure cleanup and
      // reporting; normal waits may not consume the forced-cleanup allowance.
      try { await sample(undefined, 10_000); } catch (error) { lifecycle.errors.push(`退出前采样失败：${error}`); }
      try { await bounded(() => writeFile(stop, 'stop'), 3_000); } catch (error) { lifecycle.errors.push(`请求停止失败：${error}`); }
      try { await closeConnection(browser, remaining(5_000, 10_000)); } catch (error) { lifecycle.errors.push(`断开CDP失败：${error}`); }
      try {
        const exited = await waitForExit(child, remaining(10_000, 10_000));
        lifecycle.exitCode = child.exitCode; lifecycle.signalCode = child.signalCode;
        let checked = await ownedProcesses('check', [...identities.values()], remaining(8_000, 10_000));
        const deadline = Date.now() + remaining(5_000, 10_000);
        while ((checked.survivors?.length ?? 0) > 0 && Date.now() < deadline) {
          await new Promise(done => setTimeout(done, remaining(150, 10_000)));
          checked = await ownedProcesses('check', [...identities.values()], remaining(8_000, 10_000));
        }
        lifecycle.beforeForcedCleanup = checked;
        if (!exited || child.exitCode !== 0 || child.signalCode !== null || checked.survivors?.length) {
          lifecycle.errors.push('宿主未以退出码0正常释放全部已采样进程；强制清理不能算验收通过');
          lifecycle.forcedTermination = Boolean(checked.survivors?.length);
          if (checked.survivors?.length) await ownedProcesses('terminate', [...identities.values()], remaining(8_000));
          await waitForExit(child, remaining(3_000));
        }
        lifecycle.final = await ownedProcesses('check', [...identities.values()], remaining(8_000));
        if (lifecycle.final.survivors?.length) lifecycle.errors.push('本次进程仍有存活身份');
      } catch (error) {
        lifecycle.errors.push(`进程退出核对失败：${error}`);
        // A diagnostic failure must not bypass bounded best-effort cleanup.
        // The helper still verifies each saved creation-time identity before kill.
        if (identities.size) {
          lifecycle.forcedTermination = true;
          try {
            await ownedProcesses('terminate', [...identities.values()], remaining(8_000));
            await waitForExit(child, remaining(3_000));
            lifecycle.final = await ownedProcesses('check', [...identities.values()], remaining(8_000));
          } catch (cleanupError) { lifecycle.errors.push(`失败兜底清理失败：${cleanupError}`); }
        }
      }
      try {
        await bounded(() => testInfo.attach('宿主日志', { body: output, contentType: 'text/plain' }), 3_000);
        const nativeLog = await bounded(() => readFile(join(temporary, 'config/desktop.log'), 'utf8'), 3_000).catch(() => '');
        await bounded(() => testInfo.attach('原生日志', { body: nativeLog, contentType: 'text/plain' }), 3_000);
      } finally {
        // Preserve stop/config evidence while a process might still own files.
        // Partial recursive deletion could remove stop before an EBUSY log error,
        // allowing an unverified host to miss its only graceful stop signal.
        try {
          if (!lifecycle.final || lifecycle.final.survivors?.length) {
            throw new Error('进程退出未核实，保留临时目录及stop信号供负责人精确处置');
          }
          await bounded(() => rm(temporary, { recursive: true, force: true }), 5_000);
        }
        catch (error) { lifecycle.errors.push(`临时目录删除失败：${error}`); }
        lifecycle.identities = [...identities.values()];
        lifecycle.pass = lifecycle.errors.length === 0 && lifecycle.exitCode === 0 && !lifecycle.forcedTermination;
        await bounded(() => testInfo.attach('宿主进程生命周期', { body: JSON.stringify(lifecycle, null, 2), contentType: 'application/json' }), 3_000);
      }
      expect(lifecycle.pass, JSON.stringify(lifecycle)).toBe(true);
    }
  },
});

export { expect };
