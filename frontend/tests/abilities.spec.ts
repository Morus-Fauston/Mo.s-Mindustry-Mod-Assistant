import { test, expect } from './desktop-fixture';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

test('能力数组同名项重排删除撤销与未知类型保留', async ({ desktopHost }, info) => {
  const { page, projectPath } = desktopHost;
  const file = join(projectPath, 'content/units/twin.json');
  const unknown = { type: 'CustomAbility', strange: { untouched: true } };
  await writeFile(file, JSON.stringify({ type: 'flying', health: 137, abilities: [
    { type: 'RegenAbility', amount: 1 }, { type: 'RegenAbility', amount: 2 }, unknown] }));
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree'); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const form = page.getByRole('tabpanel', { name: 'content/units/twin.json' });
  await expect(form.locator('[data-group]')).not.toHaveCount(0);
  const folds = form.locator('button[aria-label^="展开"]:not(:disabled)');
  while (await folds.count()) await folds.first().click();
  const array = form.locator('section[data-field="abilities"]');
  const items = array.locator('section[data-item-id]');
  await expect(items).toHaveCount(3);
  await expect(items.nth(2)).toContainText('未识别此类型');
  const firstId = await items.first().getAttribute('data-item-id');
  const first = array.locator(`[data-item-id="${firstId}"]`);
  const amount = first.locator('[data-field="amount"] input');
  await amount.fill('7'); await amount.press('Enter');
  await first.getByRole('button', { name: '下移第 1 项', exact: true }).click();
  await expect(items.nth(1)).toHaveAttribute('data-item-id', firstId!);
  await expect(first.locator('[data-item-title]')).toBeFocused();
  await first.getByRole('button', { name: '删除第 2 项', exact: true }).click();
  await expect(items).toHaveCount(2);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(items.nth(1)).toHaveAttribute('data-item-id', firstId!);
  await expect(amount).toHaveValue('7');
  await array.getByRole('button', { name: '添加能力列表项', exact: true }).click();
  await expect(items).toHaveCount(4);
  const added = items.nth(3);
  const type = added.getByRole('combobox', { name: '类型', exact: true });
  await expect(type).toHaveValue('ShieldRegenFieldAbility');
  await expect(type.locator('option')).toHaveCount(15);
  await type.selectOption('ForceFieldAbility');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).abilities).toMatchObject([
    { type: 'RegenAbility', amount: 2 }, { type: 'RegenAbility', amount: 7 }, unknown, { type: 'ForceFieldAbility' }]);
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await expect(form).toHaveCount(0);
  await tree.locator('[data-path="content/units/twin.json"]').click();
  await expect(form.locator('[data-group]')).not.toHaveCount(0);
  while (await folds.count()) await folds.first().click();
  await expect(items).toHaveCount(4);
  await expect(items.nth(2)).toContainText('未识别此类型');
  const measurements = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(), style = getComputedStyle(element);
    return { field: element.closest('[data-field]')?.getAttribute('data-field'), type: element.getAttribute('type') ?? element.tagName,
      width: rect.width, x: rect.x, y: rect.y, textStart: rect.x + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
      inset: parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft) };
  }));
  const inputs = measurements.filter(item => item.field && item.type === 'text' && item.width > 0);
  expect(inputs.length).toBeGreaterThan(5);
  expect(Math.max(...inputs.map(item => item.inset)) - Math.min(...inputs.map(item => item.inset))).toBeLessThan(.1);
  await writeFile(info.outputPath('能力全输入文本起点.json'), JSON.stringify(measurements, null, 2));
  await array.evaluate(element => element.scrollIntoView({ block: 'start' }));
  await page.screenshot({ path: info.outputPath('能力数组编辑.png') });
});
