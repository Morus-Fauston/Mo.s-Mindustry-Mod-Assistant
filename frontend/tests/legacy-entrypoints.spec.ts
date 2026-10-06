import { test, expect } from './desktop-fixture';
import { readFile, rename, mkdir, rmdir } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import type { Page } from '@playwright/test';

test.describe.configure({ timeout: 120_000, retries: 0 });
test.afterEach(async ({ desktopHost }, info) => {
  if (desktopHost.page.isClosed()) return;
  const probe = await desktopHost.page.evaluate(() => {
    const probe = (window as any).entryProbe;
    return probe ? { calls: probe.calls, trace: probe.trace, keys: probe.keys, queries: probe.queries } : null;
  });
  await info.attach('入口即时请求与按键门禁轨迹', { body: JSON.stringify(probe, null, 2), contentType: 'application/json' });
});

async function observe(page: Page) {
  await page.evaluate(() => {
    const host = window as any, request = host.pywebview.api.request, query = host.pywebview.api.request_result;
    host.entryProbe = { sessionId: null, calls: [], queries: [], holdClose: false, inFlight: {}, trace: [], keys: [] };
    const key = (event: KeyboardEvent, phase: string) => {
      if (!event.ctrlKey && !event.metaKey) return;
      host.entryProbe.keys.push({ phase, key: event.key, at: performance.now(), repeat: event.repeat,
        composing: event.isComposing, defaultPrevented: event.defaultPrevented,
        inFlight: Object.values(host.entryProbe.inFlight), modal: Boolean(document.querySelector('dialog[open]')),
        buttons: [...document.querySelectorAll('button')].filter(button => ['撤销', '保存已打开内容'].includes(button.textContent ?? ''))
          .map(button => ({ name: button.textContent, disabled: button.disabled })) });
    };
    window.addEventListener('keydown', event => key(event, 'capture'), true);
    window.addEventListener('keydown', event => key(event, 'bubble'));
    host.pywebview.api.request = async (envelope: any) => {
      const probe = host.entryProbe;
      probe.inFlight[envelope.requestId] = envelope.action;
      probe.trace.push({ phase: 'started', at: performance.now(), action: envelope.action, requestId: envelope.requestId });
      let response;
      try { response = await request(envelope); }
      finally {
        delete probe.inFlight[envelope.requestId];
        probe.trace.push({ phase: 'completed', at: performance.now(), action: envelope.action, requestId: envelope.requestId });
      }
      probe.calls.push({ ...envelope, response });
      if (response.ok && ['open_project', 'choose_project', 'close_project', 'create_project'].includes(envelope.action)) probe.sessionId = response.sessionId;
      if (probe.holdClose && envelope.action === 'close_project') {
        probe.holdClose = false;
        return await new Promise(resolve => { probe.release = () => resolve(response); });
      }
      return response;
    };
    host.pywebview.api.request_result = async (id: string) => {
      host.entryProbe.queries.push(id); return query(id);
    };
  });
}
async function openUnit(page: Page, projectPath: string) {
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true });
  await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const field = page.getByRole('tabpanel', { name: 'content/units/twin.json', exact: true }).getByRole('textbox', { name: '生命值', exact: true });
  await expect(field).toBeVisible(); return field;
}
async function closeProject(page: Page) {
  await page.getByRole('button', { name: '文件', exact: true }).click();
  await page.getByRole('menuitem', { name: '关闭工程', exact: true }).click();
}

test('旧入口新建打开退出快捷键与真实产品版本，模态和IME防重', async ({ desktopHost }, info) => {
  const { page, projectPath, pid } = desktopHost;
  await observe(page);
  await page.getByRole('button', { name: '关于', exact: true }).click();
  const about = page.getByRole('dialog', { name: '关于模组助手', exact: true });
  const boot = await page.evaluate(() => (window as any).pywebview.api.bootstrap(1));
  await expect(about).toContainText(boot.data.application.version);
  await expect(about).toContainText(boot.data.metadata.gameVersion);
  await page.keyboard.press('Control+Shift+n');
  await expect(page.getByRole('dialog', { name: '新建工程', exact: true })).toHaveCount(0);
  await about.getByRole('button', { name: '关闭', exact: true }).click();
  const suppressed = await page.evaluate(() => [
    new KeyboardEvent('keydown', { key: 'n', ctrlKey: true, shiftKey: true, isComposing: true, cancelable: true }),
    new KeyboardEvent('keydown', { key: 'n', ctrlKey: true, shiftKey: true, repeat: true, cancelable: true }),
  ].map(event => { window.dispatchEvent(event); return event.defaultPrevented; }));
  expect(suppressed).toEqual([true, true]);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.keyboard.press('Control+Shift+n');
  const create = page.getByRole('dialog', { name: '新建工程', exact: true });
  await expect(create).toBeVisible();
  await create.getByRole('button', { name: '取消', exact: true }).click();
  await page.keyboard.press('Control+o');
  execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    resolve(import.meta.dirname, 'folder-dialog.ps1'), '-TestProcessId', String(pid),
    '-DialogName', '选择文件夹', '-Action', 'select', '-ProjectPath', projectPath],
  { windowsHide: true, timeout: 20_000, stdio: ['ignore', 'pipe', 'pipe'] });
  await expect(page.getByRole('tree', { name: '工程文件', exact: true })).toBeVisible();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true });
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const input = page.getByRole('tabpanel', { name: 'content/units/twin.json', exact: true }).getByRole('textbox', { name: '生命值', exact: true });
  await input.fill('246'); await input.press('Enter');
  // Enter queues a real async mutation; keyboard.press does not await that mutation.
  // A quit shortcut during editing.busy is deliberately rejected by fileAction.
  await expect.poll(() => page.evaluate(() => (window as any).entryProbe.calls.some((call: any) =>
    call.action === 'set_field' && call.payload.text === '246' && call.response.ok))).toBe(true);
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeEnabled();
  await page.keyboard.press('Control+q');
  const close = page.getByRole('dialog', { name: '关闭工作台', exact: true });
  await expect(close).toBeVisible(); await close.getByRole('button', { name: '取消', exact: true }).click();
  await expect(input).toHaveValue('246');
  await page.getByRole('button', { name: '文件', exact: true }).click();
  await page.getByRole('menuitem', { name: /^退出/ }).click();
  await expect(close).toBeVisible(); await close.getByRole('button', { name: '取消', exact: true }).click();
  const inputs = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
    const style = getComputedStyle(element), rect = element.getBoundingClientRect();
    return { label: element.getAttribute('aria-label'), width: rect.width, height: rect.height,
      textStart: rect.x + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft), dpr: devicePixelRatio };
  }));
  await info.attach('全部输入文本起点', { body: JSON.stringify(inputs, null, 2), contentType: 'application/json' });
  await page.screenshot({ path: info.outputPath('旧入口快捷键.png') });
});

test('关闭工程取消保存放弃与真实保存失败，清空会话而保留宿主', async ({ desktopHost }, info) => {
  const { page, projectPath } = desktopHost; await observe(page);
  let input = await openUnit(page, projectPath);
  await input.fill('246'); await input.press('Enter');
  await closeProject(page);
  const dialog = page.getByRole('dialog', { name: '关闭工程', exact: true });
  await dialog.getByRole('button', { name: '取消', exact: true }).click();
  await expect(input).toHaveValue('246');
  await closeProject(page);
  const oldSession = await page.evaluate(() => (window as any).entryProbe.sessionId);
  const content = join(projectPath, 'content/units/twin.json');
  const backup = join(projectPath, 'content/units/twin-held.json');
  await rename(content, backup);
  let obstructionCreated = false;
  try {
    await mkdir(content); obstructionCreated = true;
    await dialog.getByRole('button', { name: '保存并继续', exact: true }).click();
    await expect(dialog.getByRole('alert')).toBeVisible();
    await expect(dialog).toBeVisible();
    expect(await page.evaluate(() => (window as any).entryProbe.sessionId)).toBe(oldSession);
  } finally {
    // Remove only the empty directory created by this test; never recursively delete content.
    if (obstructionCreated) await rmdir(content);
    await rename(backup, content);
  }
  await dialog.getByRole('button', { name: '保存并继续', exact: true }).click();
  await expect(dialog).toHaveCount(0); await expect(page.getByRole('tab')).toHaveCount(0);
  await expect(page.getByRole('tree', { name: '工程文件', exact: true })).toHaveCount(0);
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/twin.json'), 'utf8')).health).toBe(246);
  const state = await page.evaluate(async old => {
    const host = window as any, sid = host.entryProbe.sessionId;
    const call = (sessionId: string) => host.pywebview.api.request({ protocolVersion: 1, requestId: crypto.randomUUID(), sessionId, action: 'editing_state', payload: {} });
    return { current: await call(sid), old: await call(old), sid };
  }, oldSession);
  expect(state.sid).not.toBe(oldSession); expect(state.old.error.code).toBe('STALE_SESSION');
  expect(state.current.data.documents).toEqual([]); expect(state.current.data.history.canUndo).toBe(false);
  input = await openUnit(page, projectPath); await expect(input).toHaveValue('246');
  await input.fill('333'); await input.press('Enter'); await closeProject(page);
  await dialog.getByRole('button', { name: '放弃修改', exact: true }).click();
  await expect(dialog).toHaveCount(0); await expect(page.getByRole('tab')).toHaveCount(0);
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/twin.json'), 'utf8')).health).toBe(246);
  await info.attach('关闭工程请求', { body: JSON.stringify(await page.evaluate(() => (window as any).entryProbe.calls), null, 2), contentType: 'application/json' });
});

test('关闭工程超时在原裁决中查询同一请求，不重复关闭或恢复旧预览', async ({ desktopHost }, info) => {
  const { page, projectPath } = desktopHost; await observe(page);
  const input = await openUnit(page, projectPath); await input.fill('301'); await input.press('Enter');
  await page.evaluate(() => { (window as any).entryProbe.holdClose = true; });
  await closeProject(page);
  const dialog = page.getByRole('dialog', { name: '关闭工程', exact: true });
  await dialog.getByRole('button', { name: '放弃修改', exact: true }).click();
  const query = dialog.getByRole('button', { name: '查询原操作结果', exact: true });
  await expect(query).toBeVisible({ timeout: 20_000 });
  await expect(dialog.getByRole('button', { name: '放弃修改', exact: true })).toBeDisabled();
  await query.click(); await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('tab')).toHaveCount(0);
  await expect(page.getByRole('tree', { name: '工程文件', exact: true })).toHaveCount(0);
  const probe = await page.evaluate(() => {
    const probe = (window as any).entryProbe; probe.release();
    return { close: probe.calls.filter((call: any) => call.action === 'close_project'), queries: probe.queries };
  });
  expect(probe.close).toHaveLength(1); expect(probe.queries).toEqual([probe.close[0].requestId]);
  await expect(page.getByRole('tab')).toHaveCount(0);
  await info.attach('关闭超时恢复身份', { body: JSON.stringify(probe, null, 2), contentType: 'application/json' });
});
