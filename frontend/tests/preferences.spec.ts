import { test, expect } from './desktop-fixture';
import { readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import type { Locator, Page, TestInfo } from '@playwright/test';
import type { EditingState } from '../src/workspace/types';
import type { PreferencesState, WorkbenchLayout } from '../src/preferences/types';

const unitPath = 'content/units/twin.json';

async function observeBridge(page: Page) {
  await page.evaluate(() => {
    const host = window as any, request = host.pywebview.api.request;
    host.preferencesProbe = { sessionId: null, requests: [] };
    host.pywebview.api.request = async (envelope: any) => {
      const started = performance.now();
      const response = await request(envelope);
      host.preferencesProbe.requests.push({ ...envelope, started, finished: performance.now(), ok: response.ok });
      if (response.ok && envelope.action !== 'recent_projects') host.preferencesProbe.sessionId = response.sessionId;
      return response;
    };
  });
}

async function readState<T>(page: Page, action: 'preferences_state' | 'editing_state'): Promise<T> {
  return page.evaluate(async action => {
    const host = window as any;
    const result = await host.pywebview.api.request({ protocolVersion: 1, requestId: crypto.randomUUID(),
      sessionId: host.preferencesProbe.sessionId, action, payload: {} });
    if (!result.ok) throw new Error(JSON.stringify(result.error));
    return result.data;
  }, action);
}

async function openUnit(page: Page, projectPath: string) {
  await observeBridge(page);
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true });
  await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator(`[data-path="${unitPath}"]`).click();
  const form = page.getByRole('tabpanel', { name: unitPath, exact: true });
  await expect(form.locator('[data-field="health"] input[type="text"]')).toHaveValue('137');
  return form;
}

async function settings(page: Page) {
  await page.getByRole('button', { name: '设置', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '设置', exact: true });
  await expect(dialog).toBeVisible();
  return dialog;
}

async function apply(dialog: Locator) {
  await dialog.getByRole('button', { name: '应用', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '应用', exact: true })).toBeDisabled();
  await expect(dialog.getByRole('button', { name: '关闭', exact: true })).toBeEnabled();
}

async function persistedSettings(temporary: string) {
  const defaults = JSON.parse(await readFile(resolve(import.meta.dirname, '../../app/config/settings_default.json'), 'utf8'));
  const overrides = JSON.parse(await readFile(join(temporary, 'config/settings.json'), 'utf8'));
  return { ...defaults, ...overrides };
}

async function persistedLayout(temporary: string): Promise<WorkbenchLayout> {
  return JSON.parse(await readFile(join(temporary, 'config/editor_state.json'), 'utf8')).web_workbench;
}

async function measureInputs(page: Page, info: TestInfo, name: string, settingsDialog = false) {
  const measurements = await page.locator('input,textarea,select,[contenteditable="true"]').evaluateAll(elements => elements.map(element => {
    const box = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { tag: element.tagName, id: element.id, label: element.getAttribute('aria-label'),
      field: element.closest('[data-field]')?.getAttribute('data-field'),
      preference: element.closest('[data-preference]')?.getAttribute('data-preference'),
      visible: box.width > 0 && box.height > 0 && css.visibility !== 'hidden' && !element.closest('[hidden]'),
      left: box.left, top: box.top, right: box.right, width: box.width, height: box.height,
      textStart: box.left + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft),
      padding: css.paddingLeft, border: css.borderLeftWidth, dpr: devicePixelRatio, viewport: innerWidth };
  }));
  await info.attach(name, { body: JSON.stringify(measurements, null, 2), contentType: 'application/json' });
  expect(measurements.filter(row => row.visible).every(row => Number.isFinite(row.textStart))).toBe(true);
  if (settingsDialog) {
    const controls = measurements.filter(row => row.preference && row.visible);
    expect(controls.map(row => row.preference).sort()).toEqual(['auto_save_interval', 'display_name_mode', 'sprite_zoom', 'theme']);
    expect(controls.every(row => row.width > 0 && row.left >= 0 && row.right <= row.viewport + 1)).toBe(true);
    expect(Math.max(...controls.map(row => row.textStart)) - Math.min(...controls.map(row => row.textStart))).toBeLessThanOrEqual(1);
  }
}

test('设置真实四种字段显示、主题与倍率不改变业务历史并落盘', async ({ desktopHost }, info) => {
  const { page, projectPath, temporary } = desktopHost;
  const form = await openUnit(page, projectPath);
  const before = await readState<EditingState>(page, 'editing_state');
  const original = await readFile(join(projectPath, unitPath));
  const canvas = page.locator('canvas[aria-label^="贴图预览；"]');
  await expect(page.locator('[data-preview-status]')).toHaveAttribute('data-preview-status', 'ready');
  let dialog = await settings(page);
  await measureInputs(page, info, '设置全部输入文本起点-浅色', true);
  await dialog.getByRole('combobox', { name: '主题', exact: true }).selectOption('dark');
  await dialog.getByRole('textbox', { name: '预览倍率', exact: true }).fill('6');
  await dialog.getByRole('textbox', { name: '自动保存间隔', exact: true }).fill('0');
  await dialog.getByRole('combobox', { name: '字段显示名', exact: true }).selectOption('zh_en');
  await apply(dialog);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(canvas).toHaveAttribute('data-scale', '6');
  await measureInputs(page, info, '设置全部输入文本起点-深色', true);
  await page.screenshot({ path: info.outputPath('设置深色与马卡龙字段.png') });
  await dialog.getByRole('button', { name: '关闭', exact: true }).click();
  const modes = [
    ['zh_en', '生命值 (health)'], ['en_zh', 'health (生命值)'], ['zh', '生命值'], ['en', 'health'],
  ] as const;
  for (const [mode, label] of modes) {
    if (mode !== 'zh_en') {
      dialog = await settings(page);
      await dialog.getByRole('combobox', { name: '字段显示名', exact: true }).selectOption(mode);
      await apply(dialog); await dialog.getByRole('button', { name: '关闭', exact: true }).click();
    }
    await expect(form.getByRole('textbox', { name: label, exact: true })).toHaveValue('137');
    await expect.poll(async () => (await persistedSettings(temporary)).display_name_mode).toBe(mode);
    expect((await readState<PreferencesState>(page, 'preferences_state')).values.display_name_mode).toBe(mode);
  }
  dialog = await settings(page);
  await dialog.getByRole('combobox', { name: '主题', exact: true }).selectOption('light');
  await dialog.getByRole('textbox', { name: '预览倍率', exact: true }).fill('3');
  await apply(dialog); await dialog.getByRole('button', { name: '关闭', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(canvas).toHaveAttribute('data-scale', '3');
  expect(await persistedSettings(temporary)).toMatchObject({ theme: 'light', sprite_zoom: 3, auto_save_interval: 0, display_name_mode: 'en' });
  expect((await readState<EditingState>(page, 'editing_state')).history).toEqual(before.history);
  expect(await readFile(join(projectPath, unitPath))).toEqual(original);
  await measureInputs(page, info, '四显示模式后全部输入文本起点');
  await info.attach('配置独立读回', { body: JSON.stringify(await readState<PreferencesState>(page, 'preferences_state')), contentType: 'application/json' });
});

test('自动保存关闭开启再关闭按真实秒数写入当前文档', async ({ desktopHost }, info) => {
  const { page, projectPath, temporary } = desktopHost;
  const form = await openUnit(page, projectPath), input = form.locator('[data-field="health"] input[type="text"]');
  const file = join(projectPath, unitPath);
  const health = async () => JSON.parse(await readFile(file, 'utf8')).health;
  const saves = () => page.evaluate(() => (window as any).preferencesProbe.requests.filter((call: any) => call.action === 'save_opened').length);
  const interval = async (seconds: number) => {
    const dialog = await settings(page), control = dialog.getByRole('textbox', { name: '自动保存间隔', exact: true });
    if (await control.inputValue() !== String(seconds)) { await control.fill(String(seconds)); await apply(dialog); }
    await dialog.getByRole('button', { name: '关闭', exact: true }).click();
    await expect.poll(async () => (await persistedSettings(temporary)).auto_save_interval).toBe(seconds);
    await expect.poll(async () => (await readState<EditingState>(page, 'editing_state')).autoSaveInterval).toBe(seconds);
  };
  await interval(0); await input.fill('269'); await input.press('Tab');
  await expect(page.getByRole('tab').getByLabel('未保存')).toHaveCount(1);
  const before = await saves();
  // Observe a real interval longer than the subsequently enabled one-second timer.
  await page.waitForTimeout(1250);
  expect(await health()).toBe(137); expect(await saves()).toBe(before);
  await interval(1);
  await expect.poll(health, { timeout: 6_000 }).toBe(269);
  await expect.poll(saves).toBeGreaterThan(before);
  await expect(page.getByRole('tab').getByLabel('未保存')).toHaveCount(0);
  await interval(0); const after = await saves();
  await input.fill('371'); await input.press('Tab');
  await expect(page.getByRole('tab').getByLabel('未保存')).toHaveCount(1);
  await page.waitForTimeout(1250);
  expect(await health()).toBe(269); expect(await saves()).toBe(after);
  await info.attach('自动保存真实调用时序', { body: JSON.stringify(await page.evaluate(() => (window as any).preferencesProbe.requests)), contentType: 'application/json' });
});

async function drag(page: Page, separator: Locator, dx: number, dy: number) {
  await separator.scrollIntoViewIfNeeded();
  const box = await separator.boundingBox(); expect(box).not.toBeNull();
  const x = box!.x + box!.width / 2, y = box!.y + box!.height / 2;
  await page.mouse.move(x, y); await page.mouse.down();
  try { await page.mouse.move(x + dx, y + dy, { steps: 8 }); }
  finally { await page.mouse.up(); }
  await expect(separator).toHaveAttribute('data-dragging', 'false');
}

test('三分隔线键鼠独立重置与面板快捷键保留草稿和预览视口', async ({ desktopHost }, info) => {
  const { page, projectPath, temporary } = desktopHost;
  const form = await openUnit(page, projectPath), health = form.locator('[data-field="health"] input[type="text"]');
  const left = page.getByRole('separator', { name: '文件面板宽度', exact: true });
  const right = page.getByRole('separator', { name: '预览面板宽度', exact: true });
  const horizontal = page.getByRole('separator', { name: '预览与图层高度', exact: true });
  await expect(left).toHaveAttribute('aria-disabled', 'false');
  await expect(right).toHaveAttribute('aria-disabled', 'false');
  await expect(horizontal).toHaveAttribute('aria-disabled', 'false');
  const value = async (control: Locator) => Number(await control.getAttribute('aria-valuenow'));
  const leftBefore = await value(left), rightBefore = await value(right), horizontalBefore = await value(horizontal);
  await left.focus(); await left.press('ArrowRight');
  await expect.poll(() => value(left)).toBeGreaterThan(leftBefore);
  await expect.poll(async () => (await persistedLayout(temporary))?.leftWidth).toBeGreaterThan(leftBefore);
  await right.focus(); await right.press('ArrowLeft');
  await expect.poll(() => value(right)).toBeGreaterThan(rightBefore);
  await expect.poll(async () => (await persistedLayout(temporary))?.rightWidth).toBeGreaterThan(rightBefore);
  await horizontal.focus(); await horizontal.press('ArrowDown');
  await expect.poll(() => value(horizontal)).toBeGreaterThan(horizontalBefore);
  await expect.poll(async () => (await persistedLayout(temporary))?.previewRatio).toBeGreaterThan(0);
  const keyboard = await persistedLayout(temporary);
  await drag(page, left, 24, 0); await expect.poll(() => value(left)).toBeGreaterThan(keyboard.leftWidth!);
  await drag(page, right, -24, 0); await expect.poll(() => value(right)).toBeGreaterThan(keyboard.rightWidth!);
  const horizontalAfterKeys = await value(horizontal);
  await drag(page, horizontal, 0, -12); await expect.poll(() => value(horizontal)).toBeLessThan(horizontalAfterKeys);
  await expect.poll(async () => (await persistedLayout(temporary))?.previewRatio).not.toBe(keyboard.previewRatio);
  const dragged = await persistedLayout(temporary);
  await left.dblclick();
  await expect.poll(async () => (await persistedLayout(temporary))?.leftWidth).toBeNull();
  expect(await persistedLayout(temporary)).toMatchObject({ rightWidth: dragged.rightWidth, previewRatio: dragged.previewRatio });
  await right.dblclick();
  await expect.poll(async () => (await persistedLayout(temporary))?.rightWidth).toBeNull();
  expect((await persistedLayout(temporary)).previewRatio).toBe(dragged.previewRatio);
  await horizontal.dblclick();
  await expect.poll(async () => (await persistedLayout(temporary))?.previewRatio).toBeNull();
  await health.fill('1e'); await health.press('Tab');
  await expect(health).toHaveAttribute('aria-invalid', 'true');
  const canvas = page.locator('canvas[aria-label^="贴图预览；"]');
  await expect(page.getByRole('button', { name: '放大预览', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: '放大预览', exact: true }).click();
  const scale = await canvas.getAttribute('data-scale');
  await canvas.evaluate(element => element.setAttribute('data-host-lifetime-probe', 'same-canvas'));
  const filesButton = page.getByRole('button', { name: '文件面板', exact: true });
  const previewButton = page.getByRole('button', { name: '预览面板', exact: true });
  await filesButton.click(); await expect(filesButton).toHaveAttribute('aria-pressed', 'false');
  await expect(page.locator('[data-layout-panel="files"]')).toBeHidden();
  await page.keyboard.press('Control+b'); await expect(filesButton).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('[data-layout-panel="files"]')).toBeVisible();
  await previewButton.click(); await expect(previewButton).toHaveAttribute('aria-pressed', 'false');
  await expect(canvas).toBeHidden();
  await page.keyboard.press('Control+Alt+p'); await expect(previewButton).toHaveAttribute('aria-pressed', 'true');
  await expect(canvas).toBeVisible();
  await expect(canvas).toHaveAttribute('data-host-lifetime-probe', 'same-canvas');
  await expect(canvas).toHaveAttribute('data-scale', scale!);
  await expect(health).toHaveValue('1e'); await expect(health).toHaveAttribute('aria-invalid', 'true');
  expect(JSON.parse(await readFile(join(projectPath, unitPath), 'utf8')).health).toBe(137);
  await left.focus(); await left.press('ArrowRight');
  await page.getByRole('button', { name: '恢复布局', exact: true }).click();
  await expect.poll(() => persistedLayout(temporary)).toEqual({ leftWidth: null, rightWidth: null, previewRatio: null, filesVisible: true, previewVisible: true });
  await expect(health).toHaveValue('1e');
  await measureInputs(page, info, '分隔线与显隐恢复后全部输入文本起点');
  await info.attach('布局真实配置读回', { body: JSON.stringify(await readState<PreferencesState>(page, 'preferences_state')), contentType: 'application/json' });
  await page.screenshot({ path: info.outputPath('布局恢复保留非法输入.png') });
});
