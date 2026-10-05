import { test, expect } from './desktop-fixture';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

async function openWeapons(host: { page: import('@playwright/test').Page; projectPath: string }) {
  const { page, projectPath } = host;
  const file = join(projectPath, 'content/units/twin.json');
  const source = join(projectPath, 'content/weapons/laser.json');
  await writeFile(source, JSON.stringify({ name: 'laser', reload: 31, bullet: { type: 'BasicBulletType', damage: 12 } }));
  await writeFile(file, JSON.stringify({ type: 'flying', health: 137, weapons: [
    { name: 'native-test-laser', x: 2, reload: 9 }, { name: 'missing-source', x: 4 }] }));
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree'); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const form = page.getByRole('tabpanel', { name: 'content/units/twin.json' });
  await expect(form.locator('[data-group]')).not.toHaveCount(0);
  const expand = async () => {
    const folds = form.locator('button[aria-label^="展开"]:not(:disabled)');
    while (await folds.count()) await folds.first().click();
  };
  await expand();
  const array = form.locator('section[data-field="weapons"]').first();
  const items = array.locator(':scope > div > section[data-item-id]');
  await expect(items).toHaveCount(2);
  return { page, file, source, tree, form, expand, array, items };
}

test('武器引用覆盖展开与同名重排删除撤销保存', async ({ desktopHost }, info) => {
  const { page, file, source, tree, form, expand, array, items } = await openWeapons(desktopHost);
  const sourceBefore = await readFile(source, 'utf8');
  const firstId = await items.first().getAttribute('data-item-id');
  const first = array.locator(`[data-item-id="${firstId}"]`);
  const x = first.locator('[data-field="x"] input');
  await x.fill('7'); await x.press('Enter');
  await first.getByRole('button', { name: /添加.*覆盖字段/ }).first().click();
  const menu = page.getByRole('menu');
  await menu.getByRole('menuitem').first().click();
  await first.getByRole('button', { name: '展开为内联', exact: true }).click();
  await expect(first).toHaveAttribute('data-weapon-mode', 'inline');
  await expand();
  await expect(first.locator('[data-field="reload"] input').first()).toHaveValue('9');
  const damage = first.locator('[data-field="damage"] input').first();
  await damage.fill('27'); await damage.press('Enter');
  await first.getByRole('button', { name: '下移第 1 项', exact: true }).click();
  await expect(items.nth(1)).toHaveAttribute('data-item-id', firstId!);
  await expect(first.locator('[data-item-title]').first()).toBeFocused();
  await first.getByRole('button', { name: '删除第 2 项', exact: true }).click();
  await expect(items).toHaveCount(1);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(items.nth(1)).toHaveAttribute('data-item-id', firstId!);
  await expect(damage).toHaveValue('27');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).weapons[1]).toMatchObject({ x: 7, reload: 9, bullet: { damage: 27 } });
  expect(await readFile(source, 'utf8')).toBe(sourceBefore);
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await expect(form).toHaveCount(0);
  await tree.locator('[data-path="content/units/twin.json"]').click();
  await expect(form.locator('[data-group]')).not.toHaveCount(0); await expand();
  await expect(items.nth(1)).toHaveAttribute('data-weapon-mode', 'inline');
  await expect(items.nth(1).locator('[data-field="damage"] input').first()).toHaveValue('27');
  const measurements = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(), style = getComputedStyle(element);
    return { field: element.closest('[data-field]')?.getAttribute('data-field'), type: element.getAttribute('type') ?? element.tagName,
      width: rect.width, x: rect.x, y: rect.y, textStart: rect.x + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
      inset: parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft) };
  }));
  const inputs = measurements.filter(item => item.field && item.type === 'text' && item.width > 0);
  expect(inputs.length).toBeGreaterThan(5);
  expect(Math.max(...inputs.map(item => item.inset)) - Math.min(...inputs.map(item => item.inset))).toBeLessThan(.1);
  await writeFile(info.outputPath('武器全输入文本起点.json'), JSON.stringify(measurements, null, 2));
  await array.evaluate(element => element.scrollIntoView({ block: 'start' }));
  await page.screenshot({ path: info.outputPath('武器引用与内联.png') });
});

test('武器新增两模式与缺源空白确认取消', async ({ desktopHost }, info) => {
  const { page, file, expand, array, items } = await openWeapons(desktopHost);
  const missing = items.nth(1);
  await missing.getByRole('button', { name: '创建空白内联', exact: true }).click();
  const confirmation = missing.getByRole('group', { name: '确认创建空白内联', exact: true });
  await expect(confirmation.getByRole('button', { name: '取消', exact: true })).toBeFocused();
  await confirmation.press('Escape');
  await expect(confirmation).toHaveCount(0);
  await expect(missing).toHaveAttribute('data-weapon-mode', 'reference');
  await missing.getByRole('button', { name: '创建空白内联', exact: true }).click();
  await confirmation.getByRole('button', { name: '确认创建空白内联', exact: true }).click();
  await expect(missing).toHaveAttribute('data-weapon-mode', 'inline');
  await array.getByRole('button', { name: '添加武器', exact: true }).click();
  const creation = array.locator('[class*="creation_"]');
  await creation.locator('[data-reference-selector] > button').click();
  const popup = page.getByRole('dialog');
  await popup.getByRole('combobox').fill('native-test-laser');
  await popup.getByRole('option').filter({ hasText: 'native-test-laser' }).click();
  await creation.getByRole('button', { name: '确认添加', exact: true }).click();
  await expect(items).toHaveCount(3);
  await expect(items.nth(2)).toHaveAttribute('data-weapon-mode', 'reference');
  await array.getByRole('button', { name: '添加武器', exact: true }).click();
  await creation.getByRole('radio', { name: '内联新建武器', exact: true }).click();
  await creation.getByRole('textbox').fill('laser');
  await creation.getByRole('combobox').selectOption('LaserBulletType');
  const creationMeasurements = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { field: element.closest('[data-field]')?.getAttribute('data-field'), tag: element.tagName, type: element instanceof HTMLInputElement ? element.type : '', width: rect.width,
      x: rect.x, y: rect.y, textStart: rect.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft),
      inset: parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft) };
  }));
  await writeFile(info.outputPath('武器新增全输入文本起点.json'), JSON.stringify(creationMeasurements, null, 2));
  const textInputs = creationMeasurements.filter(item => item.field && item.type === 'text' && item.width > 0);
  expect(textInputs.length).toBeGreaterThan(5);
  expect(Math.max(...textInputs.map(item => item.inset)) - Math.min(...textInputs.map(item => item.inset))).toBeLessThan(.1);
  await page.screenshot({ path: info.outputPath('武器新增表单.png') });
  await creation.getByRole('button', { name: '确认添加', exact: true }).click();
  await expect(items).toHaveCount(4); await expand();
  await expect(items.nth(3)).toHaveAttribute('data-weapon-mode', 'inline');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).weapons).toMatchObject([
    { name: 'native-test-laser' }, { x: 4, bullet: { type: 'BasicBulletType' } },
    { name: 'native-test-laser' }, { name: 'laser', bullet: { type: 'LaserBulletType' } }]);
  await items.nth(3).evaluate(element => element.scrollIntoView({ block: 'start' }));
  await page.screenshot({ path: info.outputPath('武器两模式新增.png') });
});
