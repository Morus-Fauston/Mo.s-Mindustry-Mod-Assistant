import { test, expect } from './desktop-fixture';
import { execFile, execFileSync } from 'node:child_process';
import { promisify } from 'node:util';
import { join, resolve } from 'node:path';
import { readFile, writeFile } from 'node:fs/promises';
import type { Locator, Page, TestInfo } from '@playwright/test';

const executeFile = promisify(execFile);
const root = resolve(import.meta.dirname, '../..');
// The Windows venv executable launches the interpreter that owns the window.
const nativePython = execFileSync(resolve(root, '.venv-web/Scripts/python.exe'),
  ['-c', 'import sys; print(sys._base_executable)'], { windowsHide: true, encoding: 'utf8', timeout: 10_000 }).trim();
const expectedDpi = Number(process.env.MOMA_TEST_SYSTEM_DPI);
const expectedDevice = process.env.MOMA_TEST_MONITOR_DEVICE;
// The specification does not define these dimensions as CSS pixels. Keep the
// measured unit explicit; CSS mode is additional coverage, not a stronger gate.
const sizeSpace = process.env.MOMA_TEST_SIZE_SPACE ?? 'physical-window';
const dimensions = [[1280, 800], [1440, 900], [1600, 1000]] as const;
interface Rect { left: number; top: number; right: number; bottom: number; width: number; height: number }
interface NativeWindow {
  status: 'observed' | 'resized' | 'blocked-work-area'; pid: number; startTicks: string; windowHandle: string;
  outer: Rect; client: Rect; coordinateSpace: string;
  monitor: { device: string; scalePercent: number; windowDpi: number; bounds: Rect; work: Rect };
}
const domGeometry = (page: Page) => page.evaluate(() => ({ width: innerWidth, height: innerHeight,
  dpr: devicePixelRatio, screen: { width: screen.width, height: screen.height, availWidth: screen.availWidth,
    availHeight: screen.availHeight }, visual: { width: visualViewport?.width, height: visualViewport?.height,
    scale: visualViewport?.scale } }));

async function nativeWindow(pid: number, previous?: NativeWindow, outer?: { width: number; height: number }): Promise<NativeWindow> {
  const args = ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
    resolve(root, 'frontend/tests/window-size.ps1'), '-TestProcessId', String(pid),
    '-ExpectedExecutable', nativePython,
    '-ExpectedHostScript', resolve(root, 'frontend/tests/host.py')];
  if (previous) args.push('-ExpectedStartTicks', previous.startTicks, '-ExpectedWindowHandle', previous.windowHandle);
  if (outer) args.push('-Action', 'resize', '-OuterWidth', String(outer.width), '-OuterHeight', String(outer.height));
  const result = await executeFile('powershell.exe', args, { windowsHide: true, timeout: 15_000, maxBuffer: 1024 * 1024 });
  return JSON.parse(result.stdout.trim()) as NativeWindow;
}

async function calibrate(page: Page, pid: number, width: number, height: number, info: TestInfo) {
  const iterations: unknown[] = [];
  let native = await nativeWindow(pid);
  try {
    for (let attempt = 0; attempt < 5; attempt++) {
      const dom = await domGeometry(page);
      iterations.push({ attempt, native, dom });
      expect(native.coordinateSpace).toBe('physical-PMv2');
      expect(native.monitor.scalePercent, '实际系统缩放必须等于本格目标').toBe(expectedDpi);
      if (expectedDevice) expect(native.monitor.device.toLowerCase()).toBe(expectedDevice.toLowerCase());
      expect(dom.dpr).toBeCloseTo(expectedDpi / 100, 2);
      expect(dom.visual.scale).toBe(1);
      expect(['physical-window', 'css-client']).toContain(sizeSpace);
      const reached = sizeSpace === 'physical-window'
        ? native.outer.width === width && native.outer.height === height
        : dom.width === width && dom.height === height;
      if (reached) {
        const work = native.monitor.work, actual = native.outer;
        expect(actual.left >= work.left && actual.top >= work.top && actual.right <= work.right && actual.bottom <= work.bottom,
          '完整原生窗口必须位于物理工作区内').toBe(true);
        return { native, dom };
      }
      if (attempt === 4) throw new Error(`ENVIRONMENT_BLOCKED: 原生窗口经四次校准仍未达到指定${sizeSpace}尺寸，可能受原生最小尺寸约束；禁止CDP尺寸或页面倍率兜底，详情见实际读数`);
      const outer = sizeSpace === 'physical-window' ? { width, height } : {
        width: Math.round(native.client.width * width / dom.width + native.outer.width - native.client.width),
        height: Math.round(native.client.height * height / dom.height + native.outer.height - native.client.height) };
      const resized = await nativeWindow(pid, native, outer);
      iterations.push({ resize: resized });
      if (resized.status === 'blocked-work-area') {
        throw new Error(`ENVIRONMENT_BLOCKED: ${expectedDpi}%下${width}×${height} ${sizeSpace}需要原生外框${outer.width}×${outer.height}，物理工作区仅${resized.monitor.work.width}×${resized.monitor.work.height}；本格未通过`);
      }
      await page.evaluate(() => new Promise<void>(done => requestAnimationFrame(() => requestAnimationFrame(() => done()))));
      native = await nativeWindow(pid, native);
    }
    throw new Error('原生尺寸校准未返回结果');
  } finally {
    await info.attach('原生尺寸校准全部读数', { body: JSON.stringify(iterations, null, 2), contentType: 'application/json' });
  }
}

async function measureAllInputs(page: Page, info: TestInfo, label: string) {
  const rows = await page.locator('input,textarea,select,[contenteditable="true"]').evaluateAll(elements => elements.map((element, index) => {
    const control = element as HTMLElement, box = control.getBoundingClientRect(), css = getComputedStyle(control);
    const border = parseFloat(css.borderLeftWidth) || 0, padding = parseFloat(css.paddingLeft) || 0;
    return { index, tag: control.tagName, type: control.getAttribute('type'), id: control.id,
      label: control.getAttribute('aria-label'), field: control.closest('[data-field]')?.getAttribute('data-field'),
      preference: control.closest('[data-preference]')?.getAttribute('data-preference'),
      group: control.closest('[data-group]')?.getAttribute('data-group'), fieldType: control.closest('[data-field-type]')?.getAttribute('data-field-type'),
      visible: box.width > 0 && box.height > 0 && css.visibility !== 'hidden',
      inViewport: box.left >= 0 && box.top >= 0 && box.right <= innerWidth && box.bottom <= innerHeight,
      left: box.left, top: box.top, right: box.right, bottom: box.bottom, width: box.width, height: box.height,
      borderLeft: border, paddingLeft: padding, textStart: box.left + border + padding,
      font: css.fontFamily, fontSize: css.fontSize, lineHeight: css.lineHeight, textIndent: css.textIndent,
      ariaInvalid: control.getAttribute('aria-invalid'), dpr: devicePixelRatio };
  }));
  await info.attach(label, { body: JSON.stringify(rows, null, 2), contentType: 'application/json' });
  expect(rows.length, '采集全部输入而非单个样本').toBeGreaterThan(3);
  for (const row of rows.filter(row => row.visible)) {
    expect(Number.isFinite(row.textStart), `${row.field ?? row.label}文本起点`).toBe(true);
    expect(row.textStart).toBeGreaterThanOrEqual(row.left);
    expect(row.textStart).toBeLessThanOrEqual(row.right);
  }
}

async function expectInsideViewport(page: Page, element: Locator, label: string) {
  const box = await element.boundingBox(), viewport = await domGeometry(page);
  expect(box, `${label}具有实际热区`).not.toBeNull();
  expect(box!.x >= 0 && box!.y >= 0 && box!.x + box!.width <= viewport.width + 1
    && box!.y + box!.height <= viewport.height + 1, `${label}不能超出当前真实视口`).toBe(true);
}

async function drag(page: Page, separator: Locator, dx: number, dy: number, info: TestInfo) {
  if (await separator.getAttribute('aria-disabled') === 'true') {
    // The product deliberately fixes a split when both minimum panels cannot
    // fit. Verify that boundary instead of demanding an impossible resize.
    const min = await separator.getAttribute('aria-valuemin');
    const max = await separator.getAttribute('aria-valuemax');
    const value = await separator.getAttribute('aria-valuenow');
    expect(min).toBe(max); expect(value).toBe(min);
    await separator.focus(); await separator.press(dx ? 'ArrowRight' : 'ArrowDown');
    await expect(separator).toHaveAttribute('aria-valuenow', value!);
    await info.attach(`受限分隔线-${await separator.getAttribute('aria-label')}`, {
      body: JSON.stringify({ min, max, value, behavior: '空间不足时固定共同边界，键盘不能越界' }), contentType: 'application/json' });
    return;
  }
  await expect(separator).toHaveAttribute('aria-disabled', 'false');
  const before = Number(await separator.getAttribute('aria-valuenow'));
  const box = await separator.boundingBox(); expect(box).not.toBeNull();
  const x = box!.x + box!.width / 2, y = box!.y + box!.height / 2;
  await page.mouse.move(x, y); await page.mouse.down();
  try { await page.mouse.move(x + dx, y + dy, { steps: 6 }); }
  finally { await page.mouse.up(); }
  await expect(separator).toHaveAttribute('data-dragging', 'false');
  await expect.poll(async () => Number(await separator.getAttribute('aria-valuenow'))).not.toBe(before);
  await separator.dblclick();
}

test.use({ nativeZoom: 1 });
test.describe.configure({ mode: 'default', timeout: 110_000, retries: 0 });
for (const [width, height] of dimensions) for (const theme of ['light', 'dark'] as const) {
  test(`实际系统DPI ${width}×${height} ${sizeSpace} ${theme === 'light' ? '浅色' : '深色'}，缩放${process.env.MOMA_TEST_SYSTEM_DPI ?? '未指定'}%`, async ({ desktopHost }, info) => {
    const { page, pid, projectPath, nativeView } = desktopHost;
    expect([100, 125, 150, 200], '必须显式设置MOMA_TEST_SYSTEM_DPI').toContain(expectedDpi);
    expect(nativeView.zoomFactor).toBe(1);
    expect(nativeView.monitorScalePercent).toBe(expectedDpi);
    let failure: unknown;
    try {
      const calibrated = await calibrate(page, pid, width, height, info);
      const unitFile = join(projectPath, 'content/units/twin.json');
      const original = JSON.parse(await readFile(unitFile, 'utf8'));
      await writeFile(unitFile, JSON.stringify({ ...original, speed: 1.25, flying: true }));
      await page.getByRole('button').filter({ hasText: projectPath }).click();
      const tree = page.getByRole('tree', { name: '工程文件', exact: true });
      await expect(tree).toBeVisible();
      const treeFolds = tree.locator('[aria-expanded="false"]');
      for (let n = 0; n < 20 && await treeFolds.count(); n++) await treeFolds.first().click();
      await tree.locator('[data-path="content/units/twin.json"]').click();
      const form = page.getByRole('tabpanel', { name: 'content/units/twin.json', exact: true });
      const health = form.locator('[data-field="health"] input[type="text"]');
      await expect(health).toHaveValue('137');
      await page.getByRole('button', { name: '设置', exact: true }).click();
      const settings = page.getByRole('dialog', { name: '设置', exact: true });
      await expectInsideViewport(page, settings, '设置弹窗');
      await settings.getByRole('combobox', { name: '主题', exact: true }).selectOption(theme);
      const apply = settings.getByRole('button', { name: '应用', exact: true });
      if (await apply.isEnabled()) { await apply.click(); await expect(apply).toBeDisabled(); }
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
      await measureAllInputs(page, info, '设置弹窗及背景全部输入文本起点');
      await page.screenshot({ path: info.outputPath('设置弹窗.png') });
      await settings.getByRole('button', { name: '关闭', exact: true }).click();

      const folds = form.locator('button[aria-label^="展开"]:not(:disabled)');
      for (let n = 0; n < 35 && await folds.count(); n++) await folds.first().click();
      expect(await folds.count(), '展开现有组后采集全部控件').toBe(0);
      await measureAllInputs(page, info, '展开组后全部输入文本起点');
      await health.click(); await expect(health).toBeFocused();
      await health.fill('281'); await health.press('Tab');
      await expect(health).not.toHaveAttribute('aria-invalid', 'true');
      const flying = form.locator('[data-field="flying"]').getByRole('checkbox');
      await flying.click(); await expect(flying).not.toBeChecked();
      await page.getByRole('button', { name: '撤销', exact: true }).click(); await expect(flying).toBeChecked();
      const basic = form.locator('[data-group="basic"]');
      await basic.getByRole('button', { name: '折叠基础属性', exact: true }).click();
      await expect(health).toHaveCount(0);
      await basic.getByRole('button', { name: '展开基础属性', exact: true }).click();
      await expect(health).toHaveValue('281');
      await drag(page, page.getByRole('separator', { name: '文件面板宽度', exact: true }), 20, 0, info);
      await drag(page, page.getByRole('separator', { name: '预览面板宽度', exact: true }), -20, 0, info);
      await drag(page, page.getByRole('separator', { name: '预览与图层高度', exact: true }), 0, -16, info);
      for (const label of ['文件面板', '预览面板']) {
        const button = page.getByRole('button', { name: label, exact: true });
        await button.click(); await expect(button).toHaveAttribute('aria-pressed', 'false');
        await button.click(); await expect(button).toHaveAttribute('aria-pressed', 'true');
      }
      await expect(health).toHaveValue('281');
      await form.getByRole('button', { name: '添加基础属性字段', exact: true }).click();
      await expect(page.getByRole('menuitem').first()).toBeVisible();
      await expectInsideViewport(page, page.getByRole('menu'), '长字段候选菜单');
      await measureAllInputs(page, info, '字段候选全部输入文本起点');
      await page.screenshot({ path: info.outputPath('字段候选与三栏.png') });
      await page.keyboard.press('Escape');
      await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
      await expect.poll(async () => JSON.parse(await readFile(unitFile, 'utf8')).health).toBe(281);
      await health.scrollIntoViewIfNeeded();
      await measureAllInputs(page, info, '交互后全部输入文本起点');
      const finalNative = await nativeWindow(pid, calibrated.native);
      const finalDom = await domGeometry(page);
      expect(finalNative.monitor.scalePercent).toBe(expectedDpi);
      expect(finalDom).toMatchObject({ width: calibrated.dom.width, height: calibrated.dom.height, dpr: expectedDpi / 100 });
      if (sizeSpace === 'physical-window') expect(finalNative.outer).toMatchObject({ width, height });
      await info.attach('完成格尺寸与系统读数', { body: JSON.stringify({ sizeSpace, expectedDpi, expectedDevice, nativeView, finalNative, finalDom }, null, 2), contentType: 'application/json' });
      await page.screenshot({ path: info.outputPath('完整工作台.png') });
    } catch (error) {
      failure = error;
      await page.screenshot({ path: info.outputPath('未通过格现场.png') }).catch(() => undefined);
      throw error;
    } finally {
      await info.attach('矩阵格结论', { body: JSON.stringify({ sizeSpace, expectedDpi, width, height, theme,
        status: failure ? (String(failure).includes('ENVIRONMENT_BLOCKED') ? '环境阻塞-未通过' : '失败') : '交互检查通过-待fixture退出及视觉复核',
        failure: failure ? String(failure) : null, noEmulatedViewport: true, noPageZoomSubstitute: true }), contentType: 'application/json' });
    }
  });
}
