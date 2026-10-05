import { test, expect } from './desktop-fixture';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { Page, Locator } from '@playwright/test';

async function openForm(page: Page, projectPath: string, extra: Record<string, unknown> = {}) {
  const file = join(projectPath, 'content/units/twin.json');
  const original = { type: 'flying', name: '同名单元', health: 137, speed: 1.25,
    description: '字段迁移样本', flying: true, outlineColor: 'aabbcc80', engineSize: 0, engineOffset: 8, ...extra };
  await writeFile(file, JSON.stringify(original));
  await page.evaluate(() => {
    const host = window as any, request = host.pywebview.api.request;
    host.formCalls = [];
    host.pywebview.api.request = async (envelope: any) => {
      host.formCalls.push(envelope);
      const response = await request(envelope);
      if (response.ok && response.data?.documents) host.formState = response.data;
      return response;
    };
  });
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree'); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await page.locator('[data-path="content/units/twin.json"]').click();
  const form = page.getByRole('tabpanel', { name: 'content/units/twin.json' });
  await expect(form.locator('[data-group="basic"]')).toBeVisible();
  await expandGroups(form);
  return { form, file, original };
}

async function expandGroups(form: Locator) {
  const folds = form.locator('button[aria-label^="展开"]:not(:disabled)');
  while (await folds.count()) await folds.first().click();
}

function field(form: Locator, name: string) { return form.locator(`[data-field="${name}"]`); }
function input(form: Locator, name: string) { return field(form, name).locator('input[type="text"],textarea'); }
async function commit(control: Locator, text: string) {
  await control.fill(text); await control.press('Tab');
  await expect(control).not.toHaveAttribute('aria-invalid', 'true');
}
async function save(page: Page) {
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect(page.locator('footer').getByRole('status')).toContainText('已保存所有打开的内容');
}

test('基础类型真实编辑、非法草稿、颜色透明度与保存往返', async ({ desktopHost }, testInfo) => {
  const { page, projectPath } = desktopHost;
  const { form, file, original } = await openForm(page, projectPath);
  expect(JSON.parse(await readFile(file, 'utf8'))).toEqual(original);
  await expect(page.getByRole('tab').getByLabel('未保存')).toHaveCount(0);
  expect(await page.evaluate(() => (window as any).formCalls.filter((item: any) => item.action === 'set_field'))).toEqual([]);
  await input(form, 'health').fill('1e'); await input(form, 'health').press('Enter');
  await expect(input(form, 'health')).toHaveAttribute('aria-invalid', 'true');
  await expect(input(form, 'health')).toHaveValue('1e');
  expect((await page.evaluate(() => (window as any).formState)).documents[0].data.health).toBe(137);
  await input(form, 'health').press('Escape'); await expect(input(form, 'health')).toHaveValue('137');
  await commit(input(form, 'health'), '275');
  await commit(input(form, 'speed'), '2.75');
  await commit(input(form, 'description'), '中文测试，保留空格 与标点。');
  await field(form, 'flying').getByRole('checkbox').click();
  await expect(field(form, 'flying').getByRole('checkbox')).not.toBeChecked();
  await expandGroups(form);
  await input(form, 'outlineColor').fill('不是颜色');
  await input(form, 'outlineColor').press('Enter');
  await expect(input(form, 'outlineColor')).toHaveAttribute('aria-invalid', 'true');
  const picker = field(form, 'outlineColor').locator('input[type="color"]');
  await picker.fill('#123456');
  await expect(input(form, 'outlineColor')).toHaveValue(/12345680/i);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(input(form, 'outlineColor')).toHaveValue(/aabbcc80/i);
  await page.getByRole('button', { name: '重做', exact: true }).click();
  await save(page);
  const saved = JSON.parse(await readFile(file, 'utf8'));
  expect(saved).toMatchObject({ health: 275, speed: 2.75, description: '中文测试，保留空格 与标点。', flying: false });
  expect(saved.outlineColor.replace('#', '')).toBe('12345680');
  expect(saved).not.toHaveProperty('accel');
  await page.screenshot({ path: testInfo.outputPath('基础表单.png') });
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await expect(page.getByRole('tab')).toHaveCount(0);
  await page.locator('[data-path="content/units/twin.json"]').click();
  await expect(input(form, 'speed')).toHaveValue('2.75');
  await expect(input(form, 'description')).toHaveValue('中文测试，保留空格 与标点。');
});

test('能力与折叠热区独立、单向联动及缓存撤销', async ({ desktopHost }, testInfo) => {
  const { page, projectPath } = desktopHost;
  const { form, file } = await openForm(page, projectPath);
  const mining = form.locator('[data-group="mining"]'), capacity = form.locator('[data-group="capacity"]');
  await mining.getByRole('checkbox', { name: '启用采矿' }).click();
  await expect(mining.getByRole('checkbox', { name: '启用采矿' })).toBeChecked();
  await expect(capacity.getByRole('checkbox', { name: '启用容量' })).toBeChecked();
  await expect(input(form, 'mineSpeed')).toBeVisible();
  await commit(input(form, 'mineSpeed'), '6.5');
  await mining.getByRole('button', { name: '折叠采矿', exact: true }).click();
  await expect(mining.getByRole('checkbox')).toBeChecked();
  await expect(input(form, 'mineSpeed')).toHaveCount(0);
  await mining.getByRole('button', { name: '展开采矿', exact: true }).click();
  await expect(input(form, 'mineSpeed')).toHaveValue('6.5');
  await mining.getByRole('checkbox').click();
  await expect(input(form, 'mineSpeed')).toHaveCount(0);
  await expect(capacity.getByRole('checkbox')).toBeChecked();
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(mining.getByRole('checkbox')).toBeChecked();
  await expect(input(form, 'mineSpeed')).toHaveValue('6.5');
  await page.getByRole('button', { name: '重做', exact: true }).click();
  await expect(mining.getByRole('checkbox')).not.toBeChecked();
  await mining.getByRole('checkbox').click();
  await expect(input(form, 'mineSpeed')).toHaveValue('6.5');
  await mining.getByRole('button', { name: '删除采矿组', exact: true }).click();
  await expect(mining).toHaveCount(0);
  await form.getByRole('button', { name: '添加字段组', exact: true }).click();
  await expect(page.getByRole('menuitem', { name: '采矿', exact: true })).toBeVisible();
  await page.getByRole('menuitem', { name: '采矿', exact: true }).click();
  await expect(input(form, 'mineSpeed')).toHaveValue('6.5');
  await save(page);
  expect(JSON.parse(await readFile(file, 'utf8')).mineSpeed).toBe(6.5);
  await page.screenshot({ path: testInfo.outputPath('能力组恢复.png') });
});

test('字段候选、不可删除约束、依赖不生效与空字符串', async ({ desktopHost }, testInfo) => {
  const { page, projectPath } = desktopHost;
  const { form, file } = await openForm(page, projectPath);
  await expect(form.getByRole('button', { name: '删除基础属性组' })).toHaveCount(0);
  await expect(field(form, 'health').getByRole('button')).toHaveCount(0);
  await expect(field(form, 'name').getByRole('textbox')).toHaveCount(0);
  await expect(field(form, 'engineOffset')).toHaveAttribute('data-inactive', 'true');
  await expect(input(form, 'engineOffset')).toHaveValue('8');
  await expect(input(form, 'engineOffset')).not.toHaveAttribute('aria-invalid', 'true');
  await commit(input(form, 'engineSize'), '2');
  await expect(field(form, 'engineOffset')).toHaveAttribute('data-inactive', 'false');
  await form.getByRole('button', { name: '添加基础属性字段', exact: true }).click();
  const choice = page.getByRole('menuitem', { name: '是否是低空飞行', exact: true });
  await choice.focus(); await choice.press('Enter');
  await expect(field(form, 'lowAltitude').getByRole('checkbox')).toBeVisible();
  await field(form, 'lowAltitude').getByRole('button', { name: '是否是低空飞行的操作' }).click();
  await page.getByRole('menuitem', { name: '删除字段', exact: true }).click();
  await expect(field(form, 'lowAltitude')).toHaveCount(0);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(field(form, 'lowAltitude')).toBeVisible();
  await form.getByRole('button', { name: '添加基础属性字段', exact: true }).click();
  await page.getByRole('menuitem', { name: '显示星球', exact: true }).click();
  await expect(field(form, 'shownPlanets')).toBeVisible();
  await field(form, 'shownPlanets').getByRole('button', { name: '显示星球的操作' }).click();
  await page.getByRole('menuitem', { name: '删除字段', exact: true }).click();
  await expect(field(form, 'shownPlanets')).toHaveCount(0);
  await commit(input(form, 'description'), '');
  await save(page);
  const saved = JSON.parse(await readFile(file, 'utf8'));
  expect(saved.description).toBe(''); expect(saved.engineOffset).toBe(8); expect(saved.engineSize).toBe(2);
  await page.screenshot({ path: testInfo.outputPath('字段依赖与候选.png') });
});

test('真实宿主中文组合事件期间不提交、结束后保存中文', async ({ desktopHost }, testInfo) => {
  const { page, projectPath } = desktopHost;
  const { form, file } = await openForm(page, projectPath);
  const description = input(form, 'description');
  await description.focus();
  await description.dispatchEvent('compositionstart', { data: '' });
  await description.fill('zhongwen');
  await description.dispatchEvent('keydown', { key: 'Enter', code: 'Enter', isComposing: true, keyCode: 229 });
  await page.keyboard.press('Control+s');
  await expect(description).toHaveValue('zhongwen');
  const calls = await page.evaluate(() => (window as any).formCalls.filter((item: any) => item.action === 'set_field'));
  expect(calls).toEqual([]);
  await description.fill('中文输入完成');
  await description.dispatchEvent('compositionend', { data: '中文输入完成' });
  await description.press('Tab');
  await save(page);
  expect(JSON.parse(await readFile(file, 'utf8')).description).toBe('中文输入完成');
  await writeFile(testInfo.outputPath('中文组合事件边界.json'), JSON.stringify({ beforeEndCalls: calls,
    saved: '中文输入完成', boundary: '真实WebView2内注入composition事件，证明事件处理；未证明系统输入法候选窗口行为' }, null, 2));
});

test('其他聚合组不可整组删除但允许逐字段删除与撤销', async ({ desktopHost }) => {
  const { page, projectPath } = desktopHost;
  const { form } = await openForm(page, projectPath, { legLength: 4 });
  const other = form.locator('[data-group="_other"]');
  await expect(other).toBeVisible();
  await expect(other.getByRole('button', { name: '删除其他组' })).toHaveCount(0);
  const row = field(form, 'legLength');
  await row.getByRole('button').click();
  await page.getByRole('menuitem', { name: '删除字段', exact: true }).click();
  await expect(row).toHaveCount(0);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expandGroups(form);
  await expect(input(form, 'legLength')).toHaveValue('4');
});

for (const percent of [100, 125, 150, 200]) test.describe(`原生页面缩放${percent}%`, () => {
  test.use({ nativeZoom: percent / 100 });
  test('深浅主题与宿主页面缩放下全部输入起点及复选框尺寸', async ({ desktopHost }, testInfo) => {
  const { page, projectPath } = desktopHost;
  const { form, file, original } = await openForm(page, projectPath);
  const systemDpr = desktopHost.nativeView.monitorScalePercent / 100;
  const matrix: unknown[] = [];
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value; }, theme);
    {
      await expect.poll(() => page.evaluate(() => devicePixelRatio)).toBeCloseTo(systemDpr * percent / 100, 2);
      const measurements = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
        const rect = element.getBoundingClientRect(), style = getComputedStyle(element);
        const control = element.closest('[data-control]');
        const bar = control ? getComputedStyle(control, '::before') : null;
        return { label: element.getAttribute('aria-label'), type: element.getAttribute('type') ?? element.tagName,
          field: element.closest('[data-field]')?.getAttribute('data-field'),
          x: rect.x, y: rect.y, width: rect.width, height: rect.height,
          textStart: rect.x + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
          inset: parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
          barHeight: bar?.height, color: style.color, background: style.backgroundColor,
          viewport: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio } };
      }));
      const fieldInputs = measurements.filter(item => item.field && ['text', 'TEXTAREA'].includes(item.type) && item.width > 0);
      expect(fieldInputs.length).toBeGreaterThan(8);
      const insets = fieldInputs.map(item => item.inset);
      expect(Math.max(...insets) - Math.min(...insets)).toBeLessThan(.1);
      for (const item of measurements.filter(item => item.type === 'checkbox' && item.width > 0)) {
        expect(item.width).toBeCloseTo(20, 0); expect(item.height).toBeCloseTo(20, 0);
        if (item.field) expect(item.barHeight).toBe('22px');
      }
      matrix.push({ theme, pageZoomPercent: percent, systemDpr, measurements });
      await form.evaluate(element => { element.scrollTop = 0; });
      await page.screenshot({ path: testInfo.outputPath(`表单-${theme}-${percent}.png`) });
    }
  }
  await page.evaluate(() => { document.documentElement.dataset.theme = 'light'; });
  expect(JSON.parse(await readFile(file, 'utf8'))).toEqual(original);
  await expect(page.getByRole('tab').getByLabel('未保存')).toHaveCount(0);
  await writeFile(testInfo.outputPath('全输入主题缩放测量.json'), JSON.stringify({
    boundary: '实际WebView2页面缩放，系统DPI保持原值；不代替第21票四档Windows系统DPI和三窗口矩阵', matrix,
  }, null, 2));
});

});
