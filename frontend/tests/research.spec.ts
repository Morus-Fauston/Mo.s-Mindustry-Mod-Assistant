import { test, expect } from './desktop-fixture';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

async function openResearch(host: { page: import('@playwright/test').Page; projectPath: string }, research: unknown) {
  const { page, projectPath } = host;
  const file = join(projectPath, 'content/blocks/twin.json');
  await writeFile(file, JSON.stringify({ type: 'Wall', health: 100, research, shownPlanets: ['serpulo'] }));
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree'); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/blocks/twin.json"]').click();
  const form = page.getByRole('tabpanel', { name: 'content/blocks/twin.json' });
  await expect(form.locator('[data-group]')).not.toHaveCount(0);
  const expand = async () => {
    const folds = form.locator('button[aria-label^="展开"]:not(:disabled)');
    while (await folds.count()) await folds.first().click();
  };
  await expand();
  const field = form.locator('section[data-field="research"]').first();
  await expect(field).toBeVisible();
  return { page, file, form, field, tree, expand };
}

test('研究需求目标星球真实编辑校验重排保存', async ({ desktopHost }, info) => {
  const { page, file, form, field, tree, expand } = await openResearch(desktopHost,
    { parent: 'copper-wall', requirements: [{ item: 'copper', amount: 2 }, { item: 'lead', amount: 3 }],
      objectives: [{ type: 'Research', content: 'copper-wall' }] });
  const requirements = field.locator('section[data-field="requirements"]');
  const rows = requirements.locator('section[data-item-id]');
  const firstId = await rows.first().getAttribute('data-item-id');
  const first = requirements.locator(`[data-item-id="${firstId}"]`);
  const amount = first.locator('[data-field="amount"] input');
  await amount.fill('1000000'); await amount.press('Enter');
  await expect(amount).toHaveAttribute('aria-invalid', 'true');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  expect(JSON.parse(await readFile(file, 'utf8')).research.requirements[0].amount).toBe(2);
  await amount.fill('100000'); await amount.press('Enter');
  await expect(amount).toHaveAttribute('aria-invalid', 'false');
  await first.getByRole('button', { name: '下移第 1 项', exact: true }).click();
  await expect(rows.nth(1)).toHaveAttribute('data-item-id', firstId!);
  await expect(first.locator('[data-item-title]')).toBeFocused();
  const objective = field.locator('section[data-field="objectives"] section[data-item-id]').first();
  await objective.getByRole('combobox', { name: '类型', exact: true }).selectOption('OnPlanet');
  await objective.locator('[data-field="planet"] [data-reference-selector] > button').click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('combobox').fill('erekir');
  await dialog.getByRole('option').filter({ hasText: 'erekir' }).click();
  const planets = form.locator('section[data-field="shownPlanets"]');
  await planets.locator('[data-add-planet] [data-reference-selector] > button').click();
  await dialog.getByRole('combobox').fill('erekir');
  await dialog.getByRole('option').filter({ hasText: 'erekir' }).click();
  await expect(planets.locator('section[data-item-id]')).toHaveCount(2);
  await planets.getByRole('button', { name: '删除第 1 个星球', exact: true }).click();
  await expect(planets.locator('section[data-item-id]')).toHaveCount(1);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(planets.locator('section[data-item-id]')).toHaveCount(2);
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8'))).toMatchObject({
    research: { requirements: [{ item: 'lead', amount: 3 }, { item: 'copper', amount: 100000 }], objectives: [{ type: 'OnPlanet', planet: 'erekir' }] },
    shownPlanets: ['serpulo', 'erekir'] });
  expect(JSON.parse(await readFile(file, 'utf8')).research.objectives[0]).not.toHaveProperty('content');
  await page.getByRole('button', { name: '关闭全部', exact: true }).click(); await expect(form).toHaveCount(0);
  await tree.locator('[data-path="content/blocks/twin.json"]').click();
  await expect(form.locator('[data-group]')).not.toHaveCount(0); await expand();
  await expect(requirements.locator('[data-field="amount"] input').nth(1)).toHaveValue('100000');
  const measurements = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { field: element.closest('[data-field]')?.getAttribute('data-field'), type: element instanceof HTMLInputElement ? element.type : element.tagName,
      width: rect.width, x: rect.x, y: rect.y, textStart: rect.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft),
      inset: parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft) };
  }));
  await writeFile(info.outputPath('研究全输入文本起点.json'), JSON.stringify(measurements, null, 2));
  const textInputs = measurements.filter(item => item.field && item.type === 'text' && item.width > 0);
  expect(textInputs.length).toBeGreaterThan(2);
  expect(Math.max(...textInputs.map(item => item.inset)) - Math.min(...textInputs.map(item => item.inset))).toBeLessThan(.1);
  await field.evaluate(element => element.scrollIntoView({ block: 'start' }));
  await page.screenshot({ path: info.outputPath('研究需求目标编辑.png') });
});

test('研究字符串无改保留与修改撤销还原', async ({ desktopHost }, info) => {
  const { page, file, field } = await openResearch(desktopHost, 'copper-wall');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  expect(JSON.parse(await readFile(file, 'utf8')).research).toBe('copper-wall');
  await field.getByRole('button', { name: '显示更多科技树设置', exact: true }).click();
  const name = field.locator('[data-field="name"] input');
  await name.fill('中文研究标题'); await name.press('Enter');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).research).toMatchObject({ parent: 'copper-wall', name: '中文研究标题' });
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(name).toHaveValue('');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).research).toBe('copper-wall');
  await page.screenshot({ path: info.outputPath('研究字符串还原.png') });
});
