import { test as desktopTest, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cp, readFile, stat, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import type { Locator } from '@playwright/test';
import type { EditingState, ValidDocumentSnapshot } from '../src/workspace/types';

// Start before desktopHost and finish after its cleanup; this is one host, one journey.
const test = desktopTest.extend<{ journeyStarted: number }>({
  journeyStarted: [async ({}, use, info) => {
    const started = performance.now();
    try { await use(started); }
    finally {
      const path = info.outputPath('完整链结果.json');
      const report = await readFile(path, 'utf8').then(JSON.parse).catch(() => ({
        pass: false, error: '宿主准备未完成，完整链未执行',
      }));
      report.finalElapsedSeconds = (performance.now() - started) / 1000;
      report.fixtureStatus = info.status;
      report.fixtureDirectoryRemoved = Boolean(report.temporaryDirectory)
        && await stat(report.temporaryDirectory).then(() => false, error => error.code === 'ENOENT');
      report.pass = report.pass && info.status === 'passed' && report.finalElapsedSeconds <= 180
        && report.fixtureDirectoryRemoved;
      await writeFile(path, JSON.stringify(report, null, 2));
      await info.attach('最终含宿主fixture清理的完整链结果', { path, contentType: 'application/json' });
      if (info.status === 'passed') expect(report.pass, JSON.stringify(report)).toBe(true);
    }
  }, { auto: true }],
});

test.describe.configure({ timeout: 180_000, retries: 0 });
// root owns the optional fixture/host seam; it must be connected before execution.
test.use({ hostLifetimeSeconds: 180 } as Parameters<typeof test.use>[0]);
const UNIT = 'content/units/journey-unit.json';
const BLOCK = 'content/blocks/journey-crafter.json';
const SPRITE = 'sprites/units/journey-unit.png';
const python = resolve(import.meta.dirname, '../../.venv-web/Scripts/python.exe');

test('同一宿主新建到多编辑源码贴图保存导出再关闭重开完整链', async ({ desktopHost, journeyStarted }, info) => {
  const { page, temporary, pid, nativeView } = desktopHost;
  const project = join(temporary, 'acceptance-journey');
  const png = join(temporary, '完整链 中文贴图.png');
  const zip = join(temporary, '完整链 中文导出.zip');
  const report: any = { pass: false, pid, nativeView, temporaryDirectory: temporary,
    project, steps: [], snapshots: [], error: null, workDeadlineStopRequested: false };
  const errors: string[] = [];
  let phase = '宿主已就绪';
  const elapsed = () => (performance.now() - journeyStarted) / 1000;
  const budget = (maximum = 8_000) => {
    const left = 150_000 - (performance.now() - journeyStarted);
    if (left <= 0) throw new Error(`完整链工作预算耗尽：${phase}`);
    return Math.max(1, Math.min(maximum, Math.floor(left)));
  };
  const workTimer = setTimeout(() => {
    report.workDeadlineStopRequested = true;
    void writeFile(join(temporary, 'stop'), 'acceptance-journey-work-deadline')
      .catch(error => { report.deadlineStopError = String(error); });
  }, Math.max(1, 150_000 - (performance.now() - journeyStarted)));
  const onPageError = (error: Error) => errors.push(error.message);
  page.on('pageerror', onPageError);
  const assert = () => expect.configure({ timeout: budget(6_000) });
  async function step(name: string, work: () => Promise<void>) {
    phase = name; page.setDefaultTimeout(budget());
    const entry = { name, startedSeconds: elapsed(), elapsedSeconds: 0, passed: false };
    report.steps.push(entry);
    try { await work(); budget(); expect(errors).toEqual([]); entry.passed = true; }
    finally { entry.elapsedSeconds = elapsed() - entry.startedSeconds; }
  }
  async function state(): Promise<EditingState> {
    const result = await page.evaluate(async timeout => {
      const host = window as any;
      let timer: ReturnType<typeof setTimeout>;
      try {
        return await Promise.race([host.pywebview.api.request({ protocolVersion: 1,
          requestId: crypto.randomUUID(), sessionId: host.journeyProbe.sessionId,
          action: 'editing_state', payload: {} }),
        new Promise<never>((_, reject) => {
          timer = setTimeout(() => reject(new Error('完整链权威状态查询超时')), timeout);
        })]);
      } finally { clearTimeout(timer!); }
    }, budget());
    expect(result.ok, JSON.stringify(result.error)).toBe(true);
    return result.data;
  }
  async function document(path: string) {
    const current = (await state()).documents.find(value => value.path === path);
    expect(current?.validData).not.toBe(false); expect(current).toBeTruthy();
    return current as ValidDocumentSnapshot;
  }
  async function snapshot(name: string) {
    const value = await state(); report.snapshots.push({ name, elapsedSeconds: elapsed(), state: value }); return value;
  }
  async function expand(panel: Locator) {
    const folds = panel.locator('button[aria-label^="展开"]:not(:disabled)');
    while (await folds.count()) { budget(); await folds.first().click(); }
  }
  async function open(path: string) {
    const tree = page.getByRole('tree', { name: '工程文件', exact: true });
    await assert()(tree).toBeVisible();
    while (await tree.locator('[aria-expanded="false"]').count()) {
      budget(); await tree.locator('[aria-expanded="false"]').first().click();
    }
    await tree.locator(`[data-path="${path}"]`).click();
    const panel = page.getByRole('tabpanel', { name: path, exact: true });
    await assert()(panel).toBeVisible(); return panel;
  }
  async function create(category: string, kind: string, name: string) {
    await page.getByRole('button', { name: '新建内容', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '新建内容', exact: true });
    await dialog.getByRole('combobox', { name: '内容类别', exact: true }).selectOption(category);
    await dialog.getByRole('combobox', { name: '内容模板', exact: true }).selectOption(kind);
    await dialog.getByRole('textbox', { name: '内容名称', exact: true }).fill(name);
    await dialog.getByRole('button', { name: '创建内容', exact: true }).click();
    await assert()(dialog).toHaveCount(0);
    await assert()(page.getByRole('tabpanel', { name: `content/${category}/${name}.json`, exact: true })).toBeVisible();
  }
  async function native(name: string, target: string) {
    let output = '';
    try {
      output = execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        resolve(import.meta.dirname, 'folder-dialog.ps1'), '-TestProcessId', String(pid),
        '-DialogName', name, '-Action', 'select', '-ProjectPath', target],
      { windowsHide: true, encoding: 'utf8', timeout: budget(20_000), stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (error) {
      await info.attach(`完整链原生${name}失败控件`, {
        body: String((error as { stdout?: string }).stdout ?? error), contentType: 'text/plain' });
      throw error;
    }
    await info.attach(`完整链原生${name}`, { body: output, contentType: 'text/plain' });
  }
  try {
    await step('观察真实桥接并预制候选PNG', async () => {
      await page.evaluate(() => {
        const host = window as any, request = host.pywebview.api.request;
        host.journeyProbe = { sessionId: null, calls: [], inFlight: 0 };
        host.pywebview.api.request = async (envelope: any) => {
          const probe = host.journeyProbe, start = performance.now(); probe.inFlight++;
          try {
            const response = await request(envelope);
            if (response.ok && ['create_project', 'open_project', 'choose_project'].includes(envelope.action)) {
              probe.sessionId = response.sessionId;
            }
            probe.calls.push({ action: envelope.action, requestId: envelope.requestId,
              sessionId: envelope.sessionId, path: envelope.payload?.path,
              ok: response.ok, error: response.error?.code, milliseconds: performance.now() - start });
            return response;
          } finally { probe.inFlight--; }
        };
      });
      execFileSync(python, ['-c', "from PIL import Image; import sys; Image.new('RGBA',(8,6),(200,40,90,255)).save(sys.argv[1])", png],
        { windowsHide: true, timeout: budget() });
      report.testSha256 = createHash('sha256').update(await readFile(import.meta.filename)).digest('hex');
    });
    await step('原生新建工程与两个真实模板', async () => {
      await page.getByRole('button', { name: '新建工程', exact: true }).click();
      const dialog = page.getByRole('dialog', { name: '新建工程', exact: true });
      await dialog.getByRole('textbox', { name: '模组 ID', exact: true }).fill('acceptance-journey');
      await dialog.getByRole('textbox', { name: '显示名称', exact: true }).fill('完整链验收工程');
      await dialog.getByRole('textbox', { name: '作者', exact: true }).fill('自动化验收');
      await dialog.getByRole('button', { name: '选择父目录并创建', exact: true }).click();
      await native('选择文件夹', temporary);
      await assert()(dialog).toHaveCount(0);
      expect(JSON.parse(await readFile(join(project, 'mod.json'), 'utf8')).displayName).toBe('完整链验收工程');
      await create('units', 'UnitType-flying', 'journey-unit');
      await create('blocks', 'GenericCrafter', 'journey-crafter');
      const settings = page.getByRole('dialog', { name: '设置', exact: true });
      await page.getByRole('button', { name: '设置', exact: true }).click();
      const interval = settings.getByRole('textbox', { name: '自动保存间隔', exact: true });
      if (await interval.inputValue() !== '0') {
        await interval.fill('0'); await settings.getByRole('button', { name: '应用', exact: true }).click();
      }
      await settings.getByRole('button', { name: '关闭', exact: true }).click();
      const initial = await snapshot('新建后原始模板');
      expect(initial.autoSaveInterval).toBe(0); expect(initial.documents).toHaveLength(2);
      expect(initial.documents.every(value => !value.dirty)).toBe(true);
    });
    await step('普通字段与资源专用编辑器', async () => {
      const unit = await open(UNIT); await expand(unit);
      const unitHealth = unit.locator('[data-field="health"] input').first();
      await unitHealth.fill('437'); await unitHealth.press('Enter');
      await assert().poll(async () => (await document(UNIT)).data.health).toBe(437);
      const block = await open(BLOCK); await expand(block);
      const blockHealth = block.locator('[data-field="health"] input').first();
      await blockHealth.fill('654'); await blockHealth.press('Enter');
      const amount = block.locator('section[data-field="requirements"] section[data-item-id]').first().locator('[data-field="amount"] input');
      await amount.fill('77'); await amount.press('Enter');
      const power = block.locator('section[data-field="consumes"] [data-field="power"] input');
      await power.fill('2.5'); await power.press('Enter');
      await assert().poll(async () => (await document(BLOCK)).data).toMatchObject({
        health: 654, requirements: [{ item: 'copper', amount: 77 }, { item: 'lead', amount: 25 }], consumes: { power: 2.5 } });
      const edited = await snapshot('双文档表单修改未保存');
      expect(edited.documents.every(value => value.dirty)).toBe(true);
      expect(JSON.parse(await readFile(join(project, UNIT), 'utf8')).health).toBe(200);
      expect(JSON.parse(await readFile(join(project, BLOCK), 'utf8')).health).toBe(200);
    });
    await step('源码未知结构与表单共享撤销重做', async () => {
      const unit = await open(UNIT);
      const before = (await document(UNIT)).data;
      await unit.getByRole('button', { name: 'JSON 源码', exact: true }).click();
      await unit.locator('.cm-content').fill(JSON.stringify({ ...before,
        description: '完整链源码说明', journeyUnknown: { text: '保留中文未知结构', values: [1, false, null] } }));
      await assert().poll(async () => (await document(UNIT)).data.description).toBe('完整链源码说明');
      await page.getByRole('button', { name: '撤销', exact: true }).click();
      await assert().poll(async () => (await document(UNIT)).data).toEqual(before);
      await page.getByRole('button', { name: '重做', exact: true }).click();
      await assert().poll(async () => (await document(UNIT)).data.description).toBe('完整链源码说明');
      await unit.getByRole('button', { name: '表单', exact: true }).click();
      await assert()(unit.locator('[data-field="health"] input').first()).toHaveValue('437');
      await snapshot('源码重做后保留其他文档修改');
    });
    await step('原生导入PNG及同一历史撤销重做', async () => {
      const resources = page.getByRole('region', { name: '贴图资源', exact: true });
      const main = resources.locator('[data-sprite-suffix=""]');
      expect(await stat(join(project, SPRITE)).catch(() => null)).toBeNull();
      const beforeImport = await snapshot('导入前命令状态');
      await main.getByRole('button', { name: /导入.*贴图/ }).click();
      await native('打开', png);
      const expected = await readFile(png);
      await assert().poll(() => readFile(join(project, SPRITE)).catch(() => null)).toEqual(expected);
      await assert()(page.getByRole('region', { name: '贴图预览', exact: true })).toHaveAttribute('data-preview-status', 'ready');
      await page.getByRole('button', { name: '撤销', exact: true }).click();
      await assert().poll(() => stat(join(project, SPRITE)).then(() => true).catch(() => false)).toBe(false);
      const reverted = await snapshot('导入撤销仅删除PNG');
      expect(reverted.history.canRedo).toBe(true);
      expect(reverted.history.undoDescription).toBe(beforeImport.history.undoDescription);
      expect((await document(UNIT)).data.description).toBe('完整链源码说明');
      expect((await document(BLOCK)).data.health).toBe(654);
      await page.getByRole('button', { name: '重做', exact: true }).click();
      await assert().poll(() => readFile(join(project, SPRITE)).catch(() => null)).toEqual(expected);
      await assert()(page.getByRole('region', { name: '贴图预览', exact: true })).toHaveAttribute('data-preview-status', 'ready');
      const redone = await snapshot('PNG重做且双文档仍dirty');
      expect(redone.documents.every(value => value.dirty)).toBe(true);
      await page.screenshot({ path: info.outputPath('保存前真实工作台.png') });
    });
    await step('保存已打开内容与独立磁盘核验', async () => {
      await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
      await assert().poll(async () => JSON.parse(await readFile(join(project, UNIT), 'utf8')).description).toBe('完整链源码说明');
      await assert().poll(async () => JSON.parse(await readFile(join(project, BLOCK), 'utf8')).health).toBe(654);
      const unit = JSON.parse(await readFile(join(project, UNIT), 'utf8'));
      const block = JSON.parse(await readFile(join(project, BLOCK), 'utf8'));
      expect(unit).toMatchObject({ health: 437, description: '完整链源码说明',
        journeyUnknown: { text: '保留中文未知结构', values: [1, false, null] } });
      expect(block).toMatchObject({ health: 654, consumes: { power: 2.5 },
        requirements: [{ item: 'copper', amount: 77 }, { item: 'lead', amount: 25 }] });
      const saved = await snapshot('保存后双文档clean');
      expect(saved.documents).toHaveLength(2); expect(saved.documents.every(value => !value.dirty)).toBe(true);
      await assert()(page.getByRole('tab').filter({ hasText: '●' })).toHaveCount(0);
      report.persisted = { unit, block };
    });
    await step('原生导出ZIP并独立读取全部成员', async () => {
      await page.getByRole('button', { name: '导出模组', exact: true }).click();
      await native('另存为', zip);
      await assert()(page.getByText(`已导出：${zip}`, { exact: true })).toBeVisible();
      const result = execFileSync(python, ['-X', 'utf8', '-c',
        "import sys,json,zipfile,hashlib,io; from pathlib import Path; from PIL import Image; z=zipfile.ZipFile(sys.argv[1]); root=Path(sys.argv[2]); assert z.testzip() is None; names=z.namelist(); assert len(names)==len(set(names)); required=['mod.json','content/units/journey-unit.json','content/blocks/journey-crafter.json','sprites/units/journey-unit.png']; assert all(p in names for p in required); compared={};\nfor p in names:\n if p.endswith('/'): continue\n disk=root/p; assert disk.is_file(), p; value=z.read(p); assert value==disk.read_bytes(), p; compared[p]=hashlib.sha256(value).hexdigest()\nim=Image.open(io.BytesIO(z.read(required[3]))).convert('RGBA'); assert im.size==(8,6); assert set(im.getdata())=={(200,40,90,255)}; print(json.dumps({'entries':names,'memberSha256':compared,'unit':json.loads(z.read(required[1])),'block':json.loads(z.read(required[2])),'pngSize':im.size,'pngPixel':[200,40,90,255]},ensure_ascii=False))",
        zip, project], { windowsHide: true, encoding: 'utf8', timeout: budget(10_000) });
      const payload = JSON.parse(result);
      expect(payload.unit).toEqual(report.persisted.unit); expect(payload.block).toEqual(report.persisted.block);
      report.zip = { sha256: createHash('sha256').update(await readFile(zip)).digest('hex'), ...payload };
      await info.attach('独立ZIP所有成员及像素读回', { body: result, contentType: 'application/json' });
      await info.attach('完整链实际导出ZIP', { path: zip, contentType: 'application/zip' });
      for (const relative of [UNIT, BLOCK, SPRITE]) {
        await info.attach(relative, { path: join(project, relative), contentType: relative.endsWith('.png') ? 'image/png' : 'application/json' });
      }
    });
    await step('正常关闭全部并在同一宿主重开核验', async () => {
      const saved = await state();
      await page.getByRole('button', { name: '关闭全部', exact: true }).click();
      await assert()(page.getByRole('tab')).toHaveCount(0);
      await assert()(page.getByRole('dialog')).toHaveCount(0);
      await assert().poll(async () => (await state()).documents).toEqual([]);
      await assert()(page.getByRole('region', { name: '贴图预览', exact: true })).toHaveAttribute('data-preview-status', 'empty');
      const unit = await open(UNIT); await expand(unit);
      await assert()(unit.locator('[data-field="health"] input').first()).toHaveValue('437');
      await assert()(page.getByRole('region', { name: '贴图预览', exact: true })).toHaveAttribute('data-preview-status', 'ready');
      expect((await document(UNIT)).data).toEqual(report.persisted.unit);
      const block = await open(BLOCK); await expand(block);
      await assert()(block.locator('section[data-field="requirements"] section[data-item-id]').first().locator('[data-field="amount"] input')).toHaveValue('77');
      await assert()(block.locator('section[data-field="consumes"] [data-field="power"] input')).toHaveValue('2.5');
      expect((await document(BLOCK)).data).toEqual(report.persisted.block);
      const reopened = await snapshot('重开双文档核验');
      expect(reopened.sessionId).toBe(saved.sessionId);
      expect(reopened.history).toEqual(saved.history);
      expect(reopened.documents.every(value => !value.dirty)).toBe(true);
      await page.screenshot({ path: info.outputPath('导出后重开真实工作台.png') });
      await page.getByRole('button', { name: '关闭全部', exact: true }).click();
      await assert().poll(async () => (await state()).documents).toEqual([]);
      await assert()(page.getByRole('tab')).toHaveCount(0);
      const probe = await page.evaluate(() => (window as any).journeyProbe);
      expect(probe.calls.filter((call: any) => call.action === 'create_project')).toHaveLength(1);
      expect(probe.calls.filter((call: any) => call.action === 'create_content')).toHaveLength(2);
      report.sameHostSingleJourney = true;
    });
    report.pass = true;
  } catch (error) {
    report.error = { phase, message: error instanceof Error ? `${error.name}: ${error.message}` : String(error) };
    await page.screenshot({ path: info.outputPath('完整链失败现场.png'), timeout: 3_000 }).catch(() => {});
    await cp(project, info.outputPath('完整链失败工程'), { recursive: true }).catch(error => { report.failureCopyError = String(error); });
    throw error;
  } finally {
    clearTimeout(workTimer); page.off('pageerror', onPageError);
    report.workElapsedSeconds = elapsed(); report.pageErrors = errors;
    report.requests = await page.evaluate(() => (window as any).journeyProbe).catch(() => null);
    await writeFile(info.outputPath('完整链结果.json'), JSON.stringify(report, null, 2));
    // desktop-fixture closes only this host and removes its temporary directory.
    // The automatic fixture above records the final result after that cleanup.
  }
});
