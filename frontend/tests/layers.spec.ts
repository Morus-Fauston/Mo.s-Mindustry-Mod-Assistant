import { test, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

test('图层独立热区稳定武器坐标联动与视口资源保持', async ({ desktopHost }, info) => {
  const { page, projectPath } = desktopHost;
  execFileSync(resolve(import.meta.dirname, '../../.venv-web/Scripts/python.exe'), ['-c',
    `from pathlib import Path
import sys
from PIL import Image
p=Path(sys.argv[1]); (p/'sprites/weapons').mkdir()
Image.new('RGBA',(16,12),(210,30,30,255)).save(p/'sprites/units/twin.png')
Image.new('RGBA',(4,4),(20,180,30,255)).save(p/'sprites/weapons/laser.png')`, projectPath], { windowsHide: true });
  const file = join(projectPath, 'content/units/twin.json');
  await writeFile(join(projectPath, 'content/weapons/laser.json'), JSON.stringify({ name: 'laser', x: 3, y: -2, bullet: { type: 'BasicBulletType' } }));
  await writeFile(file, JSON.stringify({ type: 'flying', weapons: [{ name: 'native-test-laser', mirror: true }, { name: 'native-test-laser', x: -5, y: 4, mirror: false }] }));
  await page.evaluate(() => {
    const host = window as any, original = host.pywebview.api.request;
    host.resourceReads = 0;
    host.pywebview.api.request = async (envelope: any) => {
      if (envelope.action === 'preview_resource') host.resourceReads++;
      const response = await original(envelope);
      if (envelope.action === 'preview_scene' && response.ok) host.layerScene = response.data;
      return response;
    };
  });
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true });
  await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const layers = page.getByRole('tree', { name: '精灵图图层', exact: true });
  const rows = layers.locator('[data-layer-kind="weapon"]');
  await expect(rows).toHaveCount(2);
  const id = (await rows.first().getAttribute('data-layer-id'))!, itemId = id.slice('weapon:'.length);
  const row = layers.locator(`[data-layer-id="${id}"]`);
  const x = row.locator('[data-coordinate-key] input').nth(0), y = row.locator('[data-coordinate-key] input').nth(1);
  await expect(x).toHaveValue('3'); await expect(y).toHaveValue('-2');
  expect(JSON.parse(await readFile(file, 'utf8')).weapons[0]).not.toHaveProperty('x');
  const preview = page.getByRole('region', { name: '贴图预览', exact: true }), canvas = preview.locator('canvas');
  await expect(preview).toHaveAttribute('data-preview-status', 'ready');
  await expect(canvas).toHaveAttribute('data-visible-layers', '4');
  const resourceReads = await page.evaluate(() => (window as any).resourceReads);
  await row.getByRole('button', { name: /^选择/ }).click();
  await expect(row).toHaveAttribute('aria-selected', 'true');
  await row.getByRole('checkbox').click();
  await expect(row).toHaveAttribute('aria-selected', 'true');
  await expect(canvas).toHaveAttribute('data-visible-layers', '2');
  await layers.locator('[data-layer-id="group:weapons"] button[aria-expanded="true"]').click();
  await expect(rows).toHaveCount(0);
  await layers.locator('[data-layer-id="group:weapons"] button[aria-expanded="false"]').click();
  await expect(row.getByRole('checkbox')).not.toBeChecked();
  await row.getByRole('checkbox').click();
  await expect(canvas).toHaveAttribute('data-visible-layers', '4');
  await preview.getByRole('button', { name: '缩小预览', exact: true }).click();
  const viewport = await canvas.evaluate(element => [element.dataset.scale, element.dataset.offsetX, element.dataset.offsetY]);
  await x.fill('-6'); await x.press('Enter');
  await expect(x).toHaveValue('-6');
  await expect.poll(() => page.evaluate(() => (window as any).layerScene?.tree?.find((n: any) => n.id === 'group:weapons')?.children[0].weapon.coordinates.x.value)).toBe(-6);
  await expect.poll(() => canvas.evaluate(element => [element.dataset.scale, element.dataset.offsetX, element.dataset.offsetY])).toEqual(viewport);
  expect(await page.evaluate(() => (window as any).resourceReads)).toBe(resourceReads);
  await row.getByRole('button', { name: /^定位/ }).click();
  const form = page.getByRole('tabpanel', { name: 'content/units/twin.json' });
  const formItem = form.locator(`section[data-item-id="${itemId}"]`);
  await expect(formItem.locator('[data-field="x"] input').first()).toBeFocused();
  await formItem.getByRole('button', { name: '下移第 1 项', exact: true }).click();
  await expect(rows.nth(1)).toHaveAttribute('data-layer-id', id);
  await expect(row.locator('[data-coordinate-key] input').first()).toHaveValue('-6');
  await layers.locator('[data-layer-id="group:weapons"] button[aria-expanded="true"]').click();
  await formItem.getByRole('button', { name: '定位第 2 项图层', exact: true }).click();
  await expect(row).toHaveAttribute('aria-selected', 'true');
  await expect(row).toBeVisible();
  const otherId = await rows.first().getAttribute('data-layer-id');
  await rows.first().getByRole('button', { name: /^选择/ }).click();
  await page.getByRole('button', { name: '刷新预览', exact: true }).click();
  await expect(layers.locator(`[data-layer-id="${otherId}"]`)).toHaveAttribute('aria-selected', 'true');
  await formItem.getByRole('button', { name: '定位第 2 项图层', exact: true }).click();
  await expect(row).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(rows.first()).toHaveAttribute('data-layer-id', id);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(row.locator('[data-coordinate-key] input').first()).toHaveValue('3');
  await row.locator('[data-coordinate-key] input').nth(1).fill('-7'); await row.locator('[data-coordinate-key] input').nth(1).press('Enter');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).weapons[0].y).toBe(-7);
  expect(JSON.parse(await readFile(file, 'utf8')).weapons[0]).not.toHaveProperty('x');
  const measurements = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { coordinate: element.closest('[data-coordinate-key]')?.getAttribute('data-coordinate-key'), type: element instanceof HTMLInputElement ? element.type : element.tagName,
      width: rect.width, textStart: rect.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft), inset: parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft) };
  }));
  const coords = measurements.filter(item => item.coordinate && item.type === 'text' && item.width > 0);
  expect(coords).toHaveLength(4);
  expect(Math.max(...coords.map(item => item.inset)) - Math.min(...coords.map(item => item.inset))).toBeLessThan(.1);
  await writeFile(info.outputPath('图层全部输入文本起点.json'), JSON.stringify(measurements, null, 2));
  await writeFile(info.outputPath('图层权威场景.json'), JSON.stringify(await page.evaluate(() => (window as any).layerScene), null, 2));
  await layers.evaluate(element => { element.scrollTop = 0; });
  await page.screenshot({ path: info.outputPath('图层坐标与表单.png') });
  await row.getByRole('checkbox').click();
  await tree.locator('[data-path="content/blocks/twin.json"]').click();
  await expect(page.getByRole('tabpanel', { name: 'content/blocks/twin.json' })).toBeVisible();
  await page.getByRole('button', { name: '关闭 content/blocks/twin.json', exact: true }).click();
  await expect(form).toBeVisible();
  await expect(row.getByRole('checkbox')).not.toBeChecked();
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await expect(form).toHaveCount(0);
  await tree.locator('[data-path="content/units/twin.json"]').click();
  await expect(layers.locator('[data-layer-kind="weapon"]').first().locator('[data-coordinate-key] input').nth(1)).toHaveValue('-7');
});
