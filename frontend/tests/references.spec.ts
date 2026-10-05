import { test, expect } from './desktop-fixture';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { Page } from '@playwright/test';

async function openReference(host: { page: Page; projectPath: string }) {
  const { page, projectPath } = host;
  const file = join(projectPath, 'content/blocks/twin.json');
  await writeFile(file, JSON.stringify({ type: 'Wall', health: 823, itemDrop: 'missing-item', lightLiquid: 'water' }));
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true }); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await page.locator('[data-path="content/blocks/twin.json"]').click();
  const form = page.getByRole('tabpanel', { name: 'content/blocks/twin.json' });
  await expect(form.locator('[data-group]')).not.toHaveCount(0);
  const folds = form.locator('button[aria-label^="展开"]:not(:disabled)');
  while (await folds.count()) await folds.first().click();
  const trigger = form.locator('[data-field="itemDrop"] [data-reference-selector] > button');
  await expect(trigger).toContainText('未知引用');
  return { page, file, form, trigger };
}

test('引用双语搜索、明确选择、清空与真实保存撤销', async ({ desktopHost }, info) => {
  const { page, file, form, trigger } = await openReference(desktopHost);
  await expect(page.getByRole('tab').getByLabel('未保存')).toHaveCount(0);
  await trigger.click();
  const popup = page.getByRole('dialog');
  const search = popup.getByRole('combobox');
  await search.fill('不存在的内容');
  await expect(popup).toContainText('没有匹配的内容');
  await expect(page.getByRole('tab').getByLabel('未保存')).toHaveCount(0);
  await popup.getByRole('button', { name: '清空搜索', exact: true }).click();
  await expect(search).toHaveValue('');
  await search.fill('铜');
  await expect(popup.getByRole('option')).toHaveCount(1);
  await expect(popup.getByRole('option')).toContainText('copper');
  await search.press('Enter');
  await expect(popup).toBeVisible(); // Search alone never selects the first candidate.
  await search.press('ArrowDown'); await search.press('Enter');
  await expect(popup).toHaveCount(0);
  await expect(trigger).toContainText('copper');
  await expect(trigger).toBeFocused();
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).itemDrop).toBe('copper');
  await trigger.click();
  const clearValue = popup.getByRole('button', { name: '清除引用值', exact: true });
  for (let attempt = 0; attempt < 12 && !(await clearValue.evaluate(element => element === document.activeElement)); attempt++) {
    await page.keyboard.press('Tab');
  }
  await expect(clearValue).toBeFocused(); await page.keyboard.press('Enter');
  await expect(popup).toHaveCount(0);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(trigger).toContainText('copper');
  await trigger.click(); await search.fill('LEAD');
  await expect(popup.getByRole('option')).toHaveCount(1);
  await popup.getByRole('option').click();
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).itemDrop).toBe('lead');
  expect(JSON.parse(await readFile(file, 'utf8')).lightLiquid).toBe('water');
  await page.screenshot({ path: info.outputPath('真实引用选择.png') });
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await expect(page.getByRole('tab')).toHaveCount(0);
  await page.locator('[data-path="content/blocks/twin.json"]').click();
  await expect(form.locator('[data-group="basic"]')).toBeVisible();
  const folds = form.locator('button[aria-label^="展开"]:not(:disabled)');
  while (await folds.count()) await folds.first().click();
  await expect(trigger).toContainText('lead');
});

test('引用弹层关闭、迟到检索隔离与全部输入文本起点', async ({ desktopHost }, info) => {
  const { page, trigger } = await openReference(desktopHost);
  await trigger.click();
  const popup = page.getByRole('dialog'), search = popup.getByRole('combobox');
  await search.press('Escape'); await expect(popup).toHaveCount(0); await expect(trigger).toBeFocused();
  await trigger.press('ArrowDown'); await expect(search).toBeFocused();
  await page.evaluate(() => {
    const host = window as any, original = host.pywebview.api.request;
    host.pywebview.api.request = async (request: any) => {
      const result = await original(request);
      if (request.action === 'reference_candidates' && request.payload.query === 'copper') {
        host.heldQuery = true;
        return new Promise(resolve => { host.releaseQuery = () => resolve(result); });
      }
      return result;
    };
  });
  await search.fill('copper');
  await expect.poll(() => page.evaluate(() => (window as any).heldQuery)).toBe(true);
  await search.fill('lead'); await expect(popup.getByRole('option')).toHaveCount(1);
  await expect(popup.getByRole('option')).toContainText('lead');
  await page.evaluate(() => (window as any).releaseQuery());
  await expect(popup.getByRole('option')).toContainText('lead');
  const measurements = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
    const box = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { label: element.getAttribute('aria-label'), type: element.getAttribute('type'),
      x: box.x, y: box.y, width: box.width, height: box.height,
      textStart: box.x + parseFloat(css.paddingLeft) + parseFloat(css.borderLeftWidth),
      inset: parseFloat(css.paddingLeft) + parseFloat(css.borderLeftWidth) };
  }));
  expect(measurements.filter(item => item.width > 0).length).toBeGreaterThan(2);
  const box = (await popup.boundingBox())!, viewport = await page.evaluate(() => ({ w: innerWidth, h: innerHeight, dpr: devicePixelRatio }));
  expect(box.x).toBeGreaterThanOrEqual(0); expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.w); expect(box.y + box.height).toBeLessThanOrEqual(viewport.h);
  await writeFile(info.outputPath('全部输入起点与弹层.json'), JSON.stringify({ measurements, box, viewport }, null, 2));
  await page.screenshot({ path: info.outputPath('引用弹层.png') });
  await search.press('Tab'); await expect(popup.getByRole('button', { name: '清空搜索', exact: true })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(popup).toHaveCount(0); await expect(trigger).toBeFocused();
  await trigger.click(); await page.getByRole('banner').click(); await expect(popup).toHaveCount(0);
  await expect(page.getByRole('tab').getByLabel('未保存')).toHaveCount(0);
});

test.describe('引用选择器原生页面200%缩放', () => {
  test.use({ nativeZoom: 2 });
  test('窄栏弹层不裁切且键盘取消不写脏', async ({ desktopHost }, info) => {
    const { page, trigger } = await openReference(desktopHost);
    await trigger.click();
    const popup = page.getByRole('dialog');
    await expect(popup.getByRole('option').first()).toBeVisible();
    const box = (await popup.boundingBox())!, viewport = await page.evaluate(() => ({ w: innerWidth, h: innerHeight, dpr: devicePixelRatio }));
    expect(box.x + box.width).toBeLessThanOrEqual(viewport.w); expect(box.y + box.height).toBeLessThanOrEqual(viewport.h);
    await page.screenshot({ path: info.outputPath('200缩放引用弹层.png') });
    await popup.getByRole('combobox').press('Escape'); await expect(trigger).toBeFocused();
    await expect(page.getByRole('tab').getByLabel('未保存')).toHaveCount(0);
  });
});
