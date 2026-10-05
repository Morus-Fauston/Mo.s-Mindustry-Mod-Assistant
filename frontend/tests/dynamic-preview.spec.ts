import { test, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

test('动态播放单步旋转染色及原生最小化释放保持真实业务不变', async ({ desktopHost }, info) => {
  const { page, projectPath, pid } = desktopHost;
  execFileSync(resolve(import.meta.dirname, '../../.venv-web/Scripts/python.exe'), ['-c',
    `from pathlib import Path
import sys
from PIL import Image
p=Path(sys.argv[1]); (p/'sprites/weapons').mkdir(); (p/'sprites/blocks').mkdir()
for name,size,color in [('twin',(32,32),(150,160,170,255)),('twin-cell',(8,8),(60,130,210,255)),('twin-treads',(32,32),(30,60,90,255)),('twin-treads0-0',(32,32),(80,30,20,255)),('twin-treads0-1',(32,32),(20,90,30,255)),('twin-heat',(8,8),(130,40,60,255))]:
 Image.new('RGBA',size,color).save(p/'sprites/units'/f'{name}.png')
Image.new('RGBA',(4,4),(20,180,30,255)).save(p/'sprites/weapons/laser.png')
Image.new('RGBA',(24,24),(10,20,30,255)).save(p/'sprites/blocks/twin.png')
Image.new('RGBA',(8,8),(60,130,210,255)).save(p/'sprites/blocks/twin-team.png')`, projectPath], { windowsHide: true });
  const file = join(projectPath, 'content/units/twin.json');
  await writeFile(file, JSON.stringify({ type: 'tank', treadFrames: 2, engineSize: 1, engineOffset: 6,
    weapons: [{ name: 'laser', x: 4, y: 3, recoil: 2, mirror: true, bullet: { type: 'BasicBulletType' } }] }));
  const original = await readFile(file, 'utf8');
  await page.evaluate(() => {
    const host = window as any, original = host.pywebview.api.request;
    host.dynamicCalls = []; host.dynamicScene = null;
    host.pywebview.api.request = async (envelope: any) => {
      host.dynamicCalls.push({ action: envelope.action, sessionId: envelope.sessionId });
      const response = await original(envelope);
      if (envelope.action === 'preview_scene' && response.ok) host.dynamicScene = response.data;
      return response;
    };
  });
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true }); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const preview = page.getByRole('region', { name: '贴图预览', exact: true });
  const controls = page.getByRole('region', { name: '动态预览', exact: true });
  const canvas = preview.locator('canvas');
  await expect(controls.getByRole('button', { name: '开始预览', exact: true })).toBeEnabled();
  const state = () => page.evaluate(async () => {
    const host = window as any;
    return (await host.pywebview.api.request({ protocolVersion: 1, requestId: crypto.randomUUID(),
      sessionId: host.dynamicScene.sessionId, action: 'editing_state', payload: {} })).data;
  });
  const before = await state();
  const reads = await page.evaluate(() => (window as any).dynamicCalls.filter((item: any) => item.action === 'preview_resource').length);
  await controls.getByRole('button', { name: '开始预览', exact: true }).click();
  await expect.poll(async () => Number(await preview.getAttribute('data-animation-time'))).toBeGreaterThan(0);
  await controls.getByRole('button', { name: '暂停帧', exact: true }).click();
  const paused = Number(await preview.getAttribute('data-animation-time'));
  const pausedPixels = await canvas.evaluate((node: HTMLCanvasElement) => node.toDataURL());
  await page.waitForTimeout(160);
  expect(Number(await preview.getAttribute('data-animation-time'))).toBe(paused);
  expect(await canvas.evaluate((node: HTMLCanvasElement) => node.toDataURL())).toBe(pausedPixels);
  await controls.getByRole('button', { name: '开火一次', exact: true }).click();
  expect(await canvas.evaluate((node: HTMLCanvasElement) => node.toDataURL())).not.toBe(pausedPixels);
  await controls.getByRole('button', { name: '单步', exact: true }).click();
  await expect(preview).toHaveAttribute('data-animation-time', String(paused + 1));
  await controls.getByLabel('预览移动', { exact: true }).selectOption('moving');
  await controls.getByLabel('预览速度', { exact: true }).selectOption('2');
  await controls.getByLabel('预览朝向', { exact: true }).selectOption('右');
  await controls.getByLabel('预览队伍', { exact: true }).selectOption('蓝队');
  await controls.getByLabel('预览生命值', { exact: true }).selectOption('残血');
  await page.screenshot({ path: info.outputPath('动态暂停旋转.png') });
  await controls.getByRole('button', { name: '继续播放', exact: true }).click();
  const native = (command: number) => execFileSync('powershell.exe', ['-NoProfile', '-Command',
    `Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class PreviewWindow{[DllImport("user32.dll")]public static extern bool ShowWindow(IntPtr h,int c);}'; [PreviewWindow]::ShowWindow((Get-Process -Id ${pid}).MainWindowHandle,${command})`],
    { windowsHide: true, encoding: 'utf8' });
  try {
    native(3);
    native(6);
    await expect.poll(() => page.evaluate(() => (window as any).__momaWindowHidden)).toBe(true);
    await page.waitForTimeout(100);
    const hiddenTime = Number(await preview.getAttribute('data-animation-time'));
    const draws = await canvas.getAttribute('data-draw-count');
    await page.waitForTimeout(300);
    expect(Number(await preview.getAttribute('data-animation-time'))).toBe(hiddenTime);
    expect(await canvas.getAttribute('data-draw-count')).toBe(draws);
    native(3);
    await expect.poll(() => page.evaluate(() => (window as any).__momaWindowHidden)).toBe(false);
    await expect.poll(async () => Number(await preview.getAttribute('data-animation-time'))).toBeGreaterThan(hiddenTime);
    await info.attach('最小化时钟与绘制停止', { body: JSON.stringify({ hiddenTime, draws }), contentType: 'application/json' });
  } finally { native(9); }
  const sidebar = page.getByRole('complementary', { name: '预览与图层', exact: true });
  await sidebar.evaluate(node => { node.scrollTop = node.scrollHeight; });
  const clipTop = await sidebar.evaluate(node => node.getBoundingClientRect().top);
  await expect.poll(() => canvas.evaluate(node => node.getBoundingClientRect().bottom)).toBeLessThan(clipTop);
  await page.waitForTimeout(100);
  const scrolledTime = await preview.getAttribute('data-animation-time');
  const scrolledDraws = await canvas.getAttribute('data-draw-count');
  await page.waitForTimeout(200);
  expect(await preview.getAttribute('data-animation-time')).toBe(scrolledTime);
  expect(await canvas.getAttribute('data-draw-count')).toBe(scrolledDraws);
  await sidebar.evaluate(node => { node.scrollTop = 0; });
  await expect.poll(async () => Number(await preview.getAttribute('data-animation-time'))).toBeGreaterThan(Number(scrolledTime));
  await info.attach('滚动隐藏预览停止绘制', { body: JSON.stringify({ scrolledTime, scrolledDraws }), contentType: 'application/json' });
  await controls.getByRole('button', { name: '复位', exact: true }).click();
  await expect(preview).toHaveAttribute('data-animation-enabled', 'false');
  await expect(preview).toHaveAttribute('data-animation-time', '0');
  expect(await state()).toEqual(before);
  expect(await readFile(file, 'utf8')).toBe(original);
  expect(await page.evaluate(() => (window as any).dynamicCalls.filter((item: any) => item.action === 'preview_resource').length)).toBe(reads);
  await controls.getByRole('button', { name: '开始预览', exact: true }).click();
  await tree.locator('[data-path="content/blocks/twin.json"]').click();
  await expect(preview).toHaveAttribute('data-animation-enabled', 'false');
  await expect(controls.getByRole('button', { name: '开始预览', exact: true })).toBeEnabled();
  await controls.getByRole('button', { name: '开始预览', exact: true }).click();
  await controls.getByRole('button', { name: '暂停帧', exact: true }).click();
  await controls.getByLabel('预览队伍', { exact: true }).selectOption('蓝队');
  const pixel = await canvas.evaluate((node: HTMLCanvasElement) => {
    const scale = Number(node.dataset.scale), x = Number(node.dataset.offsetX), y = Number(node.dataset.offsetY);
    const ratio = node.width / node.getBoundingClientRect().width;
    return [...node.getContext('2d')!.getImageData(Math.floor((x + 12 * scale) * ratio), Math.floor((y + 12 * scale) * ratio), 1, 1).data];
  });
  expect(pixel).toEqual([161, 209, 246, 255]); // Independent Qt 6.11.1 pixel fixture.
  await info.attach('真实WebView2非白像素与Qt参考', { body: JSON.stringify(pixel), contentType: 'application/json' });
  const inputs = await page.locator('input,textarea,select,[contenteditable="true"]').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { label: element.getAttribute('aria-label'), field: element.closest('[data-field]')?.getAttribute('data-field'),
      width: rect.width, textStart: rect.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft), inset: parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft) };
  }));
  expect(inputs.filter(item => item.width > 0).every(item => Number.isFinite(item.textStart))).toBe(true);
  await info.attach('全部输入起点', { body: JSON.stringify(inputs), contentType: 'application/json' });
  await page.screenshot({ path: info.outputPath('动态队伍染色.png') });
  await page.getByRole('button', { name: '关闭 content/blocks/twin.json', exact: true }).click();
  await expect(preview).toHaveAttribute('data-animation-enabled', 'false');
});
