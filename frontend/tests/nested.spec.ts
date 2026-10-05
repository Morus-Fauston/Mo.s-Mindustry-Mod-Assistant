import { test, expect } from './desktop-fixture';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

async function openWeapon(host: { page: import('@playwright/test').Page; projectPath: string }) {
  const { page, projectPath } = host;
  const file = join(projectPath, 'content/weapons/laser.json');
  await writeFile(file, JSON.stringify({ type: 'Weapon', reload: 31, bullet: { type: 'BasicBulletType', damage: 12,
    status: 'burning', spawnBullets: [{ type: 'BasicBulletType', damage: 1 }, { type: 'BasicBulletType', damage: 2 }] } }));
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree'); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/weapons/laser.json"]').click();
  const form = page.getByRole('tabpanel', { name: 'content/weapons/laser.json' });
  await expect(form.locator('[data-object-path]')).not.toHaveCount(0);
  const folds = form.locator('button[aria-label^="展开"]:not(:disabled)');
  while (await folds.count()) await folds.first().click();
  return { page, form, file };
}

test('多态子弹嵌套编辑引用保存重开与类型撤销', async ({ desktopHost }, info) => {
  const { page, form, file } = await openWeapon(desktopHost);
  const bullet = form.locator('[data-object-path]').filter({ has: page.locator(':scope > [class*="typeRow"]') }).first();
  await bullet.locator(':scope > div > select').selectOption('LaserBulletType');
  const damage = bullet.locator(':scope > [aria-label="内容字段"] > [data-group] [data-field="damage"] input').first();
  await damage.fill('37.5'); await damage.press('Enter');
  await expect(damage).toHaveValue('37.5');
  const status = bullet.locator('[data-field="status"] [data-reference-selector] > button').first();
  await status.click();
  const popup = page.getByRole('dialog');
  await popup.getByRole('combobox').fill('freezing');
  await popup.getByRole('option').filter({ hasText: 'freezing' }).click();
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).bullet).toMatchObject({ type: 'LaserBulletType', damage: 37.5, status: 'freezing' });
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await page.locator('[data-path="content/weapons/laser.json"]').click();
  await expect(form.locator('select').first()).toHaveValue('LaserBulletType');
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(form.locator('select').first()).toHaveValue('BasicBulletType');
  await page.screenshot({ path: info.outputPath('嵌套子弹编辑.png') });
});

test('数组重排保持项身份，删除撤销与折叠焦点独立', async ({ desktopHost }, info) => {
  const { page, form, file } = await openWeapon(desktopHost);
  const array = form.locator('[data-field="spawnBullets"]').first();
  const items = array.locator(':scope > div > section[data-item-id]');
  await expect(items).toHaveCount(2);
  const firstId = await items.first().getAttribute('data-item-id');
  const first = array.locator(`[data-item-id="${firstId}"]`);
  await first.getByRole('button', { name: '下移第 1 项', exact: true }).click();
  await expect(items.nth(1)).toHaveAttribute('data-item-id', firstId!);
  await expect(first.locator('[data-item-title]')).toBeFocused();
  const damage = first.locator('[data-field="damage"] input').first();
  await damage.fill('19'); await damage.press('Enter');
  await first.locator('[data-item-title]').click();
  await expect(damage).not.toBeVisible();
  await first.locator('[data-item-title]').click();
  await expect(damage).toHaveValue('19');
  await first.getByRole('button', { name: '删除第 2 项', exact: true }).click();
  await expect(items).toHaveCount(1);
  await expect(items.first().locator('[data-item-title]')).toBeFocused();
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(items.nth(1)).toHaveAttribute('data-item-id', firstId!);
  await expect(damage).toHaveValue('19');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).bullet.spawnBullets.map((item: { damage: number }) => item.damage)).toEqual([2, 19]);
  const measurements = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
    const box = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { label: element.getAttribute('aria-label'), width: box.width, height: box.height,
      textStart: box.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft), dpr: devicePixelRatio };
  }));
  await info.attach('全部输入起点', { body: JSON.stringify(measurements), contentType: 'application/json' });
  await page.screenshot({ path: info.outputPath('数组身份与折叠.png') });
});

test('单位类型真实切换，未知子弹类型保留而不自动选择', async ({ desktopHost }) => {
  const { page, projectPath } = desktopHost;
  const unitFile = join(projectPath, 'content/units/twin.json');
  await writeFile(join(projectPath, 'content/weapons/laser.json'), JSON.stringify({ bullet: { type: 'CustomBullet', damage: 3 } }));
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree'); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const panel = page.getByRole('tabpanel');
  await panel.getByRole('combobox', { name: '类型', exact: true }).selectOption('tank');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(unitFile, 'utf8')).type).toBe('tank');
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(panel.getByRole('combobox', { name: '类型', exact: true })).toHaveValue('flying');
  await tree.locator('[data-path="content/weapons/laser.json"]').click();
  const weapon = page.getByRole('tabpanel', { name: 'content/weapons/laser.json' });
  const folds = weapon.locator('button[aria-label^="展开"]:not(:disabled)');
  await expect(weapon.locator('[data-group]')).not.toHaveCount(0);
  while (await folds.count()) await folds.first().click();
  await expect(weapon.getByRole('combobox', { name: '类型', exact: true })).toHaveValue('CustomBullet');
  await expect(weapon).toContainText('未识别类型');
  await expect(page.getByRole('tab', { name: 'laser', exact: true })).not.toContainText('●');
});
