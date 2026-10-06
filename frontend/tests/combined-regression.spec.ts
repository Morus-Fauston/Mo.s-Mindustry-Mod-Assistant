import { test as desktopTest, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { appendFile, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import type { Page } from '@playwright/test';

async function beforeDeadline<T>(work: () => Promise<T>, deadline: number, maximum: number, label: string): Promise<T> {
  const remaining = Math.min(maximum, deadline - Date.now());
  if (remaining <= 0) throw new Error(`预算耗尽：${label}`);
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([work(), new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error(`预算耗尽：${label}`)), remaining);
    })]);
  } finally { clearTimeout(timer); }
}

// Automatic fixtures start before desktopHost, so startup consumes the same budget.
const test = desktopTest.extend<{ regressionStarted: number }>({
  regressionStarted: [async ({}, use, info) => {
    const started = performance.now();
    const deadline = Date.now() + 600_000;
    info.annotations.push({ type: 'moma-test-absolute-deadline', description: String(deadline) });
    // This remains armed through setup, test failure and fixture teardown.
    // The fixture publishes only its own temporary stop path.
    const workTimer = setTimeout(() => {
      const stop = info.annotations.find(value => value.type === 'moma-test-stop-path')?.description;
      if (stop) void writeFile(stop, 'combined-work-deadline').catch(() => {});
    }, 540_000);
    try { await use(started); }
    finally {
      try {
        // Automatic fixture teardown follows desktopHost teardown: include logs,
        // process shutdown and its actual temporary-directory removal in the total.
        const path = info.outputPath('组合回归汇总.json');
        const report = await beforeDeadline(() => readFile(path, 'utf8').then(JSON.parse).catch(() => ({
          planned: 50, completed: 0, failedRound: 0, pass: false, error: '宿主准备阶段未完成', cleanup: {},
        })), deadline, 1_000, '读取最终汇总');
        report.fixtureStatus = info.status;
        report.cleanup.fixtureDirectoryRemoved = Boolean(report.temporaryDirectory)
          && await beforeDeadline(() => stat(report.temporaryDirectory).then(() => false, error => error.code === 'ENOENT'), deadline, 1_000, '确认临时目录删除');
        report.finalElapsedSeconds = (performance.now() - started) / 1000;
        report.timedOut ||= report.finalElapsedSeconds > 600;
        report.pass = report.pass && info.status === 'passed' && !report.timedOut && report.cleanup.fixtureDirectoryRemoved;
        await beforeDeadline(() => writeFile(path, JSON.stringify(report, null, 2)), deadline, 1_000, '写入最终汇总');
        await beforeDeadline(() => info.attach('最终含fixture清理的50轮结果', { path, contentType: 'application/json' }), deadline, 1_000, '附加最终汇总');
        if (info.status === 'passed') expect(report.pass, JSON.stringify(report)).toBe(true);
      } finally { clearTimeout(workTimer); }
    }
  }, { auto: true }],
});
test.describe.configure({ timeout: 600_000, retries: 0 });
// Requires the explicit optional fixture seam documented in work/21; no watchdog bypass.
test.use({ hostLifetimeSeconds: 600 });
const UNIT = 'content/units/twin.json', BLOCK = 'content/blocks/twin.json';
const python = resolve(import.meta.dirname, '../../.venv-web/Scripts/python.exe');
const errorText = (error: unknown) => error instanceof Error ? `${error.name}: ${error.message}` : String(error);

function processMetrics(hostPid: number, timeout: number) {
  const script = `$all=Get-CimInstance Win32_Process; $ids=[System.Collections.Generic.HashSet[int]]::new(); [void]$ids.Add(${hostPid}); do { $added=$false; foreach($p in $all) { if($ids.Contains([int]$p.ParentProcessId) -and $ids.Add([int]$p.ProcessId)) { $added=$true } } } while($added); @($all | Where-Object { $ids.Contains([int]$_.ProcessId) } | ForEach-Object { $p=Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue; if($p) { [pscustomobject]@{pid=$p.Id;parentPid=$_.ParentProcessId;name=$p.ProcessName;workingSet=$p.WorkingSet64;privateBytes=$p.PrivateMemorySize64;handles=$p.HandleCount} } }) | ConvertTo-Json -Compress`;
  const raw = execFileSync('powershell.exe', ['-NoProfile', '-Command', script], { windowsHide: true, encoding: 'utf8', timeout });
  const values = raw.trim() ? JSON.parse(raw) : [];
  return (Array.isArray(values) ? values : [values]) as { pid: number; parentPid: number; name: string; workingSet: number; privateBytes: number; handles: number }[];
}

function alive(pid: number) {
  try { process.kill(pid, 0); return true; }
  catch (error) { return (error as NodeJS.ErrnoException).code !== 'ESRCH'; }
}

async function identity(timeout: () => number) {
  const root = resolve(import.meta.dirname, '../..'), hashes: Record<string, string> = {};
  async function walk(relative: string) {
    for (const entry of await readdir(join(root, relative), { withFileTypes: true })) {
      timeout();
      if (entry.name === '__pycache__') continue;
      const name = `${relative}/${entry.name}`;
      if (entry.isDirectory()) await walk(name);
      else if (entry.isFile()) hashes[name] = createHash('sha256').update(await readFile(join(root, name))).digest('hex');
    }
  }
  for (const path of ['app/desktop', 'frontend/src', 'frontend/dist']) await walk(path);
  return { node: process.version, head: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8', windowsHide: true, timeout: timeout() }).trim(),
    status: execFileSync('git', ['status', '--porcelain'], { cwd: root, encoding: 'utf8', windowsHide: true, timeout: timeout() }), hashes };
}

async function observe(page: Page) {
  await page.evaluate(() => {
    const host = window as any, request = host.pywebview.api.request;
    host.combinedProbe = { sessionId: null, inFlight: 0, calls: [], lastScene: null, generationRequestId: null };
    host.pywebview.api.request = async (envelope: any) => {
      const probe = host.combinedProbe, start = performance.now(); probe.inFlight++;
      try {
        const response = await request(envelope);
        probe.calls.push({ action: envelope.action, requestId: envelope.requestId, path: envelope.payload?.path,
          sessionId: envelope.sessionId, milliseconds: performance.now() - start, ok: response.ok, error: response.error?.code });
        if (response.ok) {
          if (['open_project', 'choose_project', 'create_project'].includes(envelope.action) || probe.sessionId === null) probe.sessionId = response.sessionId;
          if (envelope.action === 'preview_scene') probe.lastScene = response.data;
          if (envelope.action === 'preview_generation') probe.generationRequestId = envelope.requestId;
        }
        return response;
      } finally { probe.inFlight--; }
    };
  });
}

test('最终单宿主连续50轮组合回归，工作540秒总预算600秒', async ({ desktopHost, regressionStarted }, info) => {
  const { page, temporary, projectPath, pid, nativeView } = desktopHost;
  const elapsed = () => (performance.now() - regressionStarted) / 1000;
  const absoluteDeadline = Number(info.annotations.find(value => value.type === 'moma-test-absolute-deadline')!.description);
  const summary: any = { planned: 50, completed: 0, failedRound: null, elapsedSeconds: 0, timedOut: false,
    error: null, pass: false, pid, nativeView, temporaryDirectory: temporary, cleanup: { documentRelease: false, stopRequested: false,
      processesExited: false, survivingPids: [],
      processCoverage: '仅本执行器采样的PID数字；进程创建身份、正常退出码及强制清理情况另见宿主进程生命周期附件，不宣称系统全部资源无泄漏',
      fixtureDirectoryRemoval: '由fixture finally后续执行，未在本报告冒报' } };
  const jsonl = info.outputPath('组合回归轮次.jsonl'), summaryPath = info.outputPath('组合回归汇总.json');
  const knownPids = new Set<number>([pid]), errors: string[] = [];
  const onPageError = (error: Error) => errors.push(`pageerror: ${error.message}`);
  const onConsole = (message: import('@playwright/test').ConsoleMessage) => { if (message.type() === 'error') errors.push(`console.error: ${message.text()}`); };
  page.on('pageerror', onPageError); page.on('console', onConsole);
  let round: any = null, phase = 'setup', lastDescription = '', failure: unknown = null;
  const budget = (maximum = 8_000, cleanup = false) => {
    const left = Math.min(((cleanup ? 580 : 540) - elapsed()) * 1000, absoluteDeadline - Date.now());
    if (left <= 0) { summary.timedOut = true; throw new Error(`预算耗尽：${phase}`); }
    return Math.max(1, Math.min(maximum, Math.floor(left)));
  };
  const assert = () => expect.configure({ timeout: budget(5_000) });
  async function step(name: string, work: () => Promise<void>) {
    phase = name; page.setDefaultTimeout(budget()); const start = performance.now();
    try {
      await beforeDeadline(work, absoluteDeadline - 60_000, budget(540_000), name);
      budget(); if (errors.length) throw new Error(errors.join('\n'));
    }
    finally { if (round) round.steps.push({ name, milliseconds: performance.now() - start }); }
  }
  async function query(action: string, payload: Record<string, unknown> = {}, owner?: string | null) {
    return page.evaluate(async ({ action, payload, owner, timeout }) => {
      const host = window as any;
      let timer: ReturnType<typeof setTimeout>;
      try { return await Promise.race([host.pywebview.api.request({ protocolVersion: 1, requestId: crypto.randomUUID(),
        sessionId: owner === undefined ? host.combinedProbe.sessionId : owner, action, payload }),
        new Promise<never>((_, reject) => { timer = setTimeout(() => reject(new Error(`只读查询超时：${action}`)), timeout); })]); }
      finally { clearTimeout(timer!); }
    }, { action, payload, owner, timeout: budget() });
  }
  async function state() { const value = await query('editing_state'); expect(value.ok).toBe(true); return value.data; }
  async function expandTree() {
    const tree = page.getByRole('tree', { name: '工程文件', exact: true });
    await assert()(tree).toBeVisible();
    while (await tree.locator('[aria-expanded="false"]').count()) { budget(); await tree.locator('[aria-expanded="false"]').first().click(); }
    return tree;
  }
  async function open(path: string) {
    const tree = await expandTree(); await tree.locator(`[data-path="${path}"]`).click();
    const panel = page.getByRole('tabpanel', { name: path, exact: true }); await assert()(panel).toBeVisible(); return panel;
  }
  async function closeAll() {
    await page.getByRole('button', { name: '关闭全部', exact: true }).click();
    await assert()(page.getByRole('tab')).toHaveCount(0);
    expect((await state()).documents).toEqual([]);
    const preview = page.getByRole('region', { name: '贴图预览', exact: true });
    await assert()(preview).toHaveAttribute('data-preview-status', 'empty');
    await assert()(preview).toHaveAttribute('data-animation-enabled', 'false');
  }
  const native = (name: string, target: string) => execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    resolve(import.meta.dirname, 'folder-dialog.ps1'), '-TestProcessId', String(pid), '-DialogName', name,
    '-Action', 'select', '-ProjectPath', target], { windowsHide: true, encoding: 'utf8', timeout: budget(20_000) });
  try {
    await writeFile(jsonl, '');
    const manifest = info.outputPath('组合回归实际代码与构建身份.json');
    await writeFile(manifest, JSON.stringify(await beforeDeadline(() => identity(() => budget()), absoluteDeadline - 60_000, budget(20_000), '代码身份'), null, 2));
    await info.attach('实际代码与构建身份', { path: manifest, contentType: 'application/json' });
    summary.initialProcesses = processMetrics(pid, budget());
    summary.initialProcesses.forEach((value: { pid: number }) => knownPids.add(value.pid));
    await step('准备真实样本与配置', async () => {
      // Fixture preparation happens before the project is opened, never during editing.
      const file = join(projectPath, UNIT), original = JSON.parse(await readFile(file, 'utf8'));
      original.description = '组合回归初始说明'; original.regressionUnknown = { preserve: '保留未知结构', values: [1, false, null] };
      await writeFile(file, JSON.stringify(original)); lastDescription = original.description;
      await writeFile(join(projectPath, 'content/units/broken.json'), '{"type":"flying","health":100}');
      const reference = join(temporary, '回归只读参考/content/units'); await mkdir(reference, { recursive: true });
      await writeFile(join(reference, 'twin.json'), '{"type":"flying","health":101}');
      await observe(page); await page.getByRole('button').filter({ hasText: projectPath }).click(); await expandTree();
      await page.getByRole('button', { name: '设置', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: '设置', exact: true });
      const interval = dialog.getByRole('textbox', { name: '自动保存间隔', exact: true });
      if (await interval.inputValue() !== '0') {
        await interval.fill('0'); await dialog.getByRole('button', { name: '应用', exact: true }).click();
      }
      await assert()(dialog.getByRole('button', { name: '关闭', exact: true })).toBeEnabled();
      await dialog.getByRole('button', { name: '关闭', exact: true }).click();
      expect((await state()).autoSaveInterval).toBe(0);
    });
    const cdp = await beforeDeadline(() => page.context().newCDPSession(page), absoluteDeadline - 60_000, budget(), '建立CDP指标会话');
    await beforeDeadline(() => cdp.send('Performance.enable'), absoluteDeadline - 60_000, budget(), '启动CDP指标');
    for (let index = 1; index <= 50; index++) {
      budget(); round = { round: index, startedSeconds: elapsed(), steps: [], passed: false };
      await step('字段与源码共享历史', async () => {
        const panel = await open(UNIT), health = panel.locator('[data-field="health"] input[type="text"]');
        await health.fill(String(1000 + index)); await health.press('Enter');
        await assert().poll(async () => (await state()).documents.find((doc: any) => doc.path === UNIT)?.data.health).toBe(1000 + index);
        await panel.getByRole('button', { name: 'JSON 源码', exact: true }).click();
        const source = panel.locator('.cm-content');
        const data = (await state()).documents.find((doc: any) => doc.path === UNIT).data;
        await source.fill(JSON.stringify({ ...data, description: `组合回归第${index}轮` }));
        await assert().poll(async () => (await state()).documents.find((doc: any) => doc.path === UNIT)?.data.description).toBe(`组合回归第${index}轮`);
        await page.getByRole('button', { name: '撤销', exact: true }).click();
        expect((await state()).documents.find((doc: any) => doc.path === UNIT).data.description).toBe(lastDescription);
        await page.getByRole('button', { name: '重做', exact: true }).click();
        await assert().poll(async () => (await state()).documents.find((doc: any) => doc.path === UNIT)?.data.description).toBe(`组合回归第${index}轮`);
        await panel.getByRole('button', { name: '表单', exact: true }).click(); await assert()(health).toHaveValue(String(1000 + index));
      });
      await step('同名切页动态与旧PNG释放', async () => {
        const block = await open(BLOCK), health = block.locator('[data-field="health"] input[type="text"]');
        await health.fill(String(2000 + index)); await health.press('Enter'); await open(UNIT);
        const preview = page.getByRole('region', { name: '贴图预览', exact: true });
        await assert()(preview).toHaveAttribute('data-preview-status', 'ready');
        await assert().poll(() => page.evaluate(() => (window as any).combinedProbe.lastScene?.path)).toBe(UNIT);
        const scene = await page.evaluate(() => (window as any).combinedProbe.lastScene);
        const resourceId = scene.layers.find((layer: any) => layer.resourceId)?.resourceId; expect(resourceId).toBeTruthy();
        const history = (await state()).history;
        const controls = page.getByRole('region', { name: '动态预览', exact: true });
        await controls.getByRole('button', { name: '开始预览', exact: true }).click();
        await assert().poll(async () => Number(await preview.getAttribute('data-animation-time'))).toBeGreaterThan(0);
        await controls.getByRole('button', { name: '暂停帧', exact: true }).click();
        const paused = await preview.getAttribute('data-animation-time');
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        expect(await preview.getAttribute('data-animation-time')).toBe(paused); expect((await state()).history).toEqual(history);
        await open(BLOCK);
        await assert().poll(() => page.evaluate(() => (window as any).combinedProbe.lastScene?.path)).toBe(BLOCK);
        const released = await query('preview_resource', { resourceId });
        expect(released.ok).toBe(false); expect(released.error.code).toBe('PREVIEW_RESOURCE_UNAVAILABLE');
        round.oldResourceReleased = { resourceId, code: released.error.code }; await open(UNIT);
      });
      await step('保存双文件并独立读回', async () => {
        await page.keyboard.press('Control+s');
        await assert().poll(async () => JSON.parse(await readFile(join(projectPath, UNIT), 'utf8')).description).toBe(`组合回归第${index}轮`);
        const unit = JSON.parse(await readFile(join(projectPath, UNIT), 'utf8')), block = JSON.parse(await readFile(join(projectPath, BLOCK), 'utf8'));
        expect(unit.health).toBe(1000 + index); expect(block.health).toBe(2000 + index);
        expect(unit.regressionUnknown).toEqual({ preserve: '保留未知结构', values: [1, false, null] });
        round.authoritative = await state(); expect(round.authoritative.documents.every((doc: any) => !doc.dirty)).toBe(true);
        round.persisted = { unitHealth: unit.health, blockHealth: block.health, description: unit.description };
      });
      if (index % 10 === 0) await step(`第${index}轮固定专项`, async () => {
        if (index === 10) {
          await page.getByRole('button', { name: '设置', exact: true }).click();
          const dialog = page.getByRole('dialog', { name: '设置', exact: true });
          await dialog.getByRole('combobox', { name: '主题', exact: true }).selectOption('dark');
          await dialog.getByRole('button', { name: '应用', exact: true }).click();
          await assert()(page.locator('html')).toHaveAttribute('data-theme', 'dark');
          await dialog.getByRole('button', { name: '关闭', exact: true }).click(); round.special = '真实主题设置';
        } else if (index === 20) {
          const panel = page.getByRole('region', { name: '贴图生成', exact: true });
          await panel.getByRole('checkbox', { name: '完整图', exact: true }).check();
          await panel.getByRole('button', { name: '预览生成结果', exact: true }).click();
          await assert()(panel.locator('img')).not.toHaveCount(0);
          await panel.getByRole('button', { name: '取消预览', exact: true }).click(); await assert()(panel.locator('img')).toHaveCount(0);
          const result = await page.evaluate(async () => { const host = window as any; return host.pywebview.api.request_result(host.combinedProbe.generationRequestId); });
          expect(result.response.error.code).toBe('RESULT_EXPIRED'); round.special = { generationResult: result };
        } else if (index === 30) {
          const panel = page.getByRole('region', { name: '只读参考与内容对比', exact: true });
          await panel.getByRole('button', { name: '打开参考目录', exact: true }).click();
          round.native = native('选择文件夹', join(temporary, '回归只读参考'));
          await panel.getByRole('combobox', { name: '内容类别', exact: true }).selectOption('units');
          await panel.getByRole('listbox', { name: '参考内容', exact: true }).selectOption('twin');
          await panel.getByRole('button', { name: '确认比较', exact: true }).click();
          await assert()(panel.getByRole('table', { name: '实际字段对比', exact: true })).toBeVisible();
          round.special = '真实参考比较与关闭释放';
        } else if (index === 40) {
          const output = join(temporary, '组合回归导出.zip');
          await page.getByRole('button', { name: '导出模组', exact: true }).click(); round.native = native('另存为', output);
          await assert()(page.getByText(`已导出：${output}`, { exact: true })).toBeVisible();
          const zip = execFileSync(python, ['-X', 'utf8', '-c', 'import json,sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; print(json.dumps(json.loads(z.read("content/units/twin.json")),ensure_ascii=False))', output], { windowsHide: true, encoding: 'utf8', timeout: budget() });
          expect(JSON.parse(zip).health).toBe(1040); round.special = { zipHealth: JSON.parse(zip).health };
        } else {
          const previous = (await state()).sessionId;
          await page.getByRole('button', { name: '打开工程', exact: true }).click(); round.native = native('选择文件夹', projectPath);
          await assert().poll(() => page.evaluate(() => (window as any).combinedProbe.sessionId)).not.toBe(previous);
          const stale = await query('editing_state', {}, previous); expect(stale.error.code).toBe('STALE_SESSION');
          round.special = { oldSession: previous, error: stale.error.code }; await open(UNIT);
        }
      });
      if (index === 1 || index % 10 === 0) await page.screenshot({ path: info.outputPath(`组合回归-${index}.png`), timeout: budget() });
      await step('关闭释放重开及最终关闭', async () => {
        await closeAll();
        if (index === 30) await assert().poll(async () => (await query('reference_sources')).data.sources.length).toBe(1);
        const reopened = await open(UNIT);
        await assert()(reopened.locator('[data-field="health"] input[type="text"]')).toHaveValue(String(1000 + index));
        expect((await state()).documents[0].data.description).toBe(`组合回归第${index}轮`);
        await closeAll(); summary.cleanup.documentRelease = true;
        await assert().poll(() => page.evaluate(() => (window as any).combinedProbe.inFlight)).toBe(0);
        const probe = await page.evaluate(() => {
          const probe = (window as any).combinedProbe, calls = probe.calls.splice(0);
          return { calls, inFlight: probe.inFlight, domNodes: document.querySelectorAll('*').length,
            heap: (performance as any).memory?.usedJSHeapSize ?? null, tags: document.querySelectorAll('[role="tab"]').length };
        });
        round.renderer = probe; round.performance = await cdp.send('Performance.getMetrics');
        round.processes = processMetrics(pid, budget()); round.processes.forEach((value: { pid: number }) => knownPids.add(value.pid));
        expect(round.processes.some((value: { pid: number }) => value.pid === pid)).toBe(true);
      });
      round.passed = true; round.endedSeconds = elapsed(); summary.completed = index; lastDescription = `组合回归第${index}轮`;
      await beforeDeadline(() => appendFile(jsonl, JSON.stringify(round) + '\n'), absoluteDeadline - 60_000, budget(), '持久化已完成轮次'); round = null;
    }
    await beforeDeadline(() => cdp.detach(), absoluteDeadline - 60_000, budget(), '释放CDP指标会话');
  } catch (cause) {
    failure = cause; summary.error = errorText(cause); summary.failedRound = round?.round ?? 0;
    if (round) {
      round.failedPhase = phase; round.error = summary.error; round.endedSeconds = elapsed();
      try { await beforeDeadline(() => appendFile(jsonl, JSON.stringify(round) + '\n'), absoluteDeadline - 20_000, budget(1_000, true), '持久化失败轮次'); }
      catch (cause) { summary.failureRoundWriteError = errorText(cause); }
    }
    if (elapsed() < 540) await page.screenshot({ path: info.outputPath('组合回归失败.png'), timeout: budget(3000) }).catch(() => {});
  } finally {
    summary.workElapsedSeconds = elapsed();
    // Signal shutdown before diagnostic work; copying a failed sample must not
    // postpone closing a native dialog or a hung renderer.
    try {
      await beforeDeadline(() => writeFile(join(temporary, 'stop'), 'combined-regression-finished'), absoluteDeadline - 20_000, budget(1_000, true), '停止宿主');
      summary.cleanup.stopRequested = true;
    } catch (cause) { summary.cleanup.stopError = errorText(cause); }
    if (failure) {
      try {
        execFileSync(python, ['-X', 'utf8', '-c', 'import shutil,sys; shutil.copytree(sys.argv[1],sys.argv[2],dirs_exist_ok=True)', projectPath, info.outputPath('失败工程')],
          { windowsHide: true, encoding: 'utf8', timeout: budget(5_000, true) });
        summary.failureProjectPreserved = true;
      } catch (cause) { summary.preserveError = errorText(cause); summary.failureProjectPreserved = false; }
    }
    if (alive(pid)) {
      try {
        summary.finalProcesses = processMetrics(pid, budget(5_000, true));
        summary.finalProcesses.forEach((value: { pid: number }) => knownPids.add(value.pid));
      } catch (cause) { summary.cleanup.processSampleError = errorText(cause); }
    }
    try {
      const cleanupDeadline = performance.now() + budget(35_000, true);
      while (performance.now() < cleanupDeadline && [...knownPids].some(alive)) await new Promise(resolve => setTimeout(resolve, 100));
      summary.cleanup.survivingPids = [...knownPids].filter(alive);
      summary.cleanup.processesExited = summary.cleanup.survivingPids.length === 0;
    } catch (cause) { summary.cleanup.error = errorText(cause); }
    page.off('pageerror', onPageError); page.off('console', onConsole);
    summary.elapsedSeconds = elapsed(); summary.errors = errors;
    summary.timedOut ||= summary.workElapsedSeconds > 540 || summary.elapsedSeconds > 600;
    summary.pass = errors.length === 0 && summary.completed === 50 && !failure && !summary.timedOut && summary.cleanup.documentRelease && summary.cleanup.processesExited;
    await beforeDeadline(() => writeFile(summaryPath, JSON.stringify(summary, null, 2)), absoluteDeadline - 15_000, 1_000, '写入实际结果');
    await beforeDeadline(() => info.attach('50轮实际结果', { path: summaryPath, contentType: 'application/json' }), absoluteDeadline - 15_000, 1_000, '附加实际结果');
    await beforeDeadline(() => info.attach('50轮逐轮证据', { path: jsonl, contentType: 'application/x-ndjson' }), absoluteDeadline - 15_000, 1_000, '附加逐轮证据');
  }
  expect(summary.pass, JSON.stringify(summary)).toBe(true);
});
