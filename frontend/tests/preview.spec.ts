import { test, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { readFile, writeFile, rename } from 'node:fs/promises';
import { join, resolve } from 'node:path';

test('真实PNG镜像层次与高DPI鼠标中心缩放', async ({ desktopHost }, testInfo) => {
  const { page, projectPath } = desktopHost;
  execFileSync(resolve(import.meta.dirname, '../../.venv-web/Scripts/python.exe'), ['-c',
    `from pathlib import Path
import sys,json
from PIL import Image
p=Path(sys.argv[1]); (p/'sprites/weapons').mkdir()
Image.new('RGBA',(16,12),(210,30,30,255)).save(p/'sprites/units/twin.png')
w=Image.new('RGBA',(4,4),(20,180,30,255))
for x in (2,3):
 for y in range(4): w.putpixel((x,y),(30,80,220,255))
w.save(p/'sprites/weapons/laser.png')
f=p/'content/units/twin.json'; d=json.loads(f.read_text(encoding='utf-8')); d['weapons']=[{'name':'laser','x':3,'y':2,'mirror':True}]; f.write_text(json.dumps(d),encoding='utf-8')`, projectPath], { windowsHide: true });
  const original = await readFile(join(projectPath, 'content/units/twin.json'), 'utf8');
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true }); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await page.locator('[data-path="content/units/twin.json"]').click();
  const preview = page.getByRole('region', { name: '贴图预览', exact: true });
  await expect(preview).toHaveAttribute('data-preview-status', 'ready');
  const canvas = preview.locator('canvas');
  const readViewport = () => canvas.evaluate((element: HTMLCanvasElement) => {
    const rect = element.getBoundingClientRect();
    return { scale: Number(element.dataset.scale), x: Number(element.dataset.offsetX), y: Number(element.dataset.offsetY),
      width: rect.width, height: rect.height, backingWidth: element.width, backingHeight: element.height, dpr: devicePixelRatio };
  });
  const initial = await readViewport();
  expect(initial.scale).toBe(4);
  expect(initial.backingWidth).toBe(Math.round(initial.width * initial.dpr));
  expect(initial.backingHeight).toBe(Math.round(initial.height * initial.dpr));
  const pixels = await canvas.evaluate((element: HTMLCanvasElement) => {
    const scale = Number(element.dataset.scale), x = Number(element.dataset.offsetX), y = Number(element.dataset.offsetY);
    const bounds = element.getBoundingClientRect(), context = element.getContext('2d')!;
    return [[8, 8], [18.5, -3], [-5.5, -3]].map(([sx, sy]) => Array.from(context.getImageData(
      Math.floor((x + sx * scale) * element.width / bounds.width),
      Math.floor((y + sy * scale) * element.height / bounds.height), 1, 1).data));
  });
  expect(pixels).toEqual([[210, 30, 30, 255], [20, 180, 30, 255], [30, 80, 220, 255]]);
  await testInfo.attach('真实PNG像素与DPI', { body: JSON.stringify({ initial, pixels }), contentType: 'application/json' });
  await writeFile(testInfo.outputPath('像素与DPI.json'), JSON.stringify({ initial, pixels }, null, 2));
  const bounds = (await canvas.boundingBox())!, anchor = { x: 80, y: 70 };
  await canvas.evaluate(element => element.addEventListener('wheel', raw => {
    const event = raw as WheelEvent, rect = element.getBoundingClientRect();
    (window as any).actualWheelAnchor = { x: event.clientX - rect.left, y: event.clientY - rect.top };
  }, { once: true }));
  await page.mouse.move(bounds.x + anchor.x, bounds.y + anchor.y); await page.mouse.wheel(0, -100);
  await expect.poll(async () => (await readViewport()).scale).toBeGreaterThan(initial.scale);
  const zoomed = await readViewport();
  const actualAnchor = await page.evaluate(() => (window as any).actualWheelAnchor as { x: number; y: number });
  expect((actualAnchor.x - zoomed.x) / zoomed.scale).toBeCloseTo((actualAnchor.x - initial.x) / initial.scale, 4);
  expect((actualAnchor.y - zoomed.y) / zoomed.scale).toBeCloseTo((actualAnchor.y - initial.y) / initial.scale, 4);
  await writeFile(testInfo.outputPath('实际滚轮锚点.json'), JSON.stringify({ initial, zoomed, requestedAnchor: anchor, actualAnchor }, null, 2));
  await page.mouse.down(); await page.mouse.move(bounds.x + anchor.x + 30, bounds.y + anchor.y + 20); await page.mouse.up();
  const moved = await readViewport();
  expect(moved.x - zoomed.x).toBeCloseTo(30, 0);
  expect(moved.y - zoomed.y).toBeCloseTo(20, 0);
  await preview.getByRole('button', { name: '适应', exact: true }).click();
  const fitted = await readViewport();
  expect(fitted.scale).toBeGreaterThan(0);
  expect({ x: fitted.x, y: fitted.y, scale: fitted.scale }).not.toEqual({ x: moved.x, y: moved.y, scale: moved.scale });
  await canvas.press('ArrowRight');
  await preview.getByRole('button', { name: '适应', exact: true }).click();
  expect(await readViewport()).toEqual(fitted);
  await preview.getByRole('button', { name: '网格', exact: true }).click();
  await expect(preview.getByRole('button', { name: '网格', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.screenshot({ path: testInfo.outputPath('真实素材静态预览.png') });
  expect(await readFile(join(projectPath, 'content/units/twin.json'), 'utf8')).toBe(original);
});

test('缺失损坏素材可刷新恢复，部分图层仍可操作', async ({ desktopHost }, testInfo) => {
  const { page, projectPath } = desktopHost;
  const png = join(projectPath, 'sprites/units/twin.png');
  const original = await readFile(png);
  await rename(png, `${png}.backup`);
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true }); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await page.locator('[data-path="content/units/twin.json"]').click();
  const preview = page.getByRole('region', { name: '贴图预览', exact: true });
  await expect(preview).toHaveAttribute('data-preview-status', 'missing');
  await expect(preview).toContainText('主体贴图');
  await writeFile(png, '<svg><script>throw 1</script></svg>');
  await page.getByRole('button', { name: '刷新预览' }).click();
  await expect(preview).toContainText('PNG 文件损坏');
  await writeFile(png, original);
  await writeFile(join(projectPath, 'sprites/units/twin-cell.png'), 'broken');
  await page.getByRole('button', { name: '刷新预览' }).click();
  await expect(preview).toHaveAttribute('data-preview-status', 'partial');
  await expect(preview.getByRole('button', { name: '适应', exact: true })).toBeEnabled();
  await page.screenshot({ path: testInfo.outputPath('坏附层保留主体.png') });
  await page.locator('[data-path="content/blocks/twin.json"]').click();
  await expect(preview).toHaveAttribute('data-preview-status', 'missing');
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await expect(preview).toHaveAttribute('data-preview-status', 'empty');
});

test('切页后迟到场景不覆盖当前内容', async ({ desktopHost }) => {
  const { page, projectPath } = desktopHost;
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true }); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await page.evaluate(() => {
    const host = window as any, original = host.pywebview.api.request;
    host.pywebview.api.request = async (envelope: any) => {
      const result = await original(envelope);
      if (envelope.action === 'preview_scene' && envelope.payload.path === 'content/units/twin.json') {
        host.pywebview.api.request = original;
        host.sceneHeld = true;
        return new Promise(resolve => { host.releaseScene = () => resolve(result); });
      }
      return result;
    };
  });
  await page.locator('[data-path="content/units/twin.json"]').click();
  await expect.poll(() => page.evaluate(() => (window as any).sceneHeld)).toBe(true);
  await page.locator('[data-path="content/blocks/twin.json"]').click();
  const preview = page.getByRole('region', { name: '贴图预览', exact: true });
  await expect(preview).toHaveAttribute('data-preview-status', 'missing');
  await page.evaluate(() => (window as any).releaseScene());
  await expect(preview.getByRole('button', { name: '适应', exact: true })).toBeDisabled();
  await expect(preview).toHaveAttribute('data-preview-status', 'missing');
  await page.locator('[data-path="content/units/twin.json"]').click();
  await expect(preview).toHaveAttribute('data-preview-status', 'ready');
});
