import { test, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { readFile, writeFile, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';

test('原生PNG替换取消、删除撤销、外部刷新及全部输入起点', async ({ desktopHost }, testInfo) => {
  const { page, projectPath, temporary, pid } = desktopHost;
  const target = join(projectPath, 'sprites/units/twin.png');
  const original = await readFile(target);
  const source = join(temporary, '中文 新贴图.png');
  execFileSync(resolve(import.meta.dirname, '../../.venv-web/Scripts/python.exe'), ['-c',
    "from PIL import Image; import sys; Image.new('RGBA',(8,6),(200,40,90,255)).save(sys.argv[1])", source], { windowsHide: true });
  const dialog = (action: string, path = source) => execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', resolve(import.meta.dirname, 'folder-dialog.ps1'), '-TestProcessId', String(pid), '-DialogName', '打开',
    '-Action', action, '-ProjectPath', path], { windowsHide: true, encoding: 'utf8', timeout: 20_000, stdio: ['ignore', 'pipe', 'pipe'] });
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree'); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const resources = page.getByRole('region', { name: '贴图资源', exact: true });
  const main = resources.locator('[data-sprite-suffix=""]');
  await expect(main.getByRole('button', { name: /替换.*贴图/ })).toBeEnabled();
  await main.getByRole('button', { name: /替换.*贴图/ }).click();
  await expect(main.getByRole('button', { name: '取消', exact: true })).toBeFocused();
  await main.getByRole('button', { name: '选择并替换' }).click();
  await testInfo.attach('原生文件取消', { body: dialog('cancel'), contentType: 'text/plain' });
  await expect(main.getByRole('button', { name: /替换.*贴图/ })).toBeEnabled();
  expect(await readFile(target)).toEqual(original);
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeDisabled();
  await main.getByRole('button', { name: /替换.*贴图/ }).click();
  await main.getByRole('button', { name: '选择并替换' }).click();
  let nativeResult = '';
  try { nativeResult = dialog('select'); } catch (error) { await testInfo.attach('原生文件控件', { body: String((error as { stdout?: string }).stdout ?? ''), contentType: 'text/plain' }); throw error; }
  await testInfo.attach('原生文件选择', { body: nativeResult, contentType: 'text/plain' });
  const replacement = await readFile(source);
  await expect.poll(() => readFile(target).catch(() => null)).toEqual(replacement);
  await expect(page.getByRole('region', { name: '贴图预览', exact: true })).toHaveAttribute('data-preview-status', 'ready');
  await expect(page.getByRole('tab')).not.toContainText('●');
  await main.getByRole('button', { name: /删除.*贴图/ }).click();
  await main.getByRole('button', { name: '确认删除' }).click();
  await expect(main.getByRole('button', { name: /导入.*贴图/ })).toBeEnabled();
  await expect.poll(() => readFile(target).then(() => true).catch(() => false)).toBe(false);
  await expect(tree.locator('[data-path="sprites/units/twin.png"]')).toHaveCount(0);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect.poll(() => readFile(target).catch(() => null)).toEqual(replacement);
  await expect(tree.locator('[data-path="sprites/units/twin.png"]')).toBeVisible();
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect.poll(() => readFile(target).catch(() => null)).toEqual(original);
  await writeFile(target, 'bad external PNG');
  await expect(page.getByRole('region', { name: '贴图预览', exact: true })).toHaveAttribute('data-preview-status', 'missing');
  await writeFile(target, replacement);
  await expect(page.getByRole('region', { name: '贴图预览', exact: true })).toHaveAttribute('data-preview-status', 'ready');
  const measurements = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { label: element.getAttribute('aria-label'), width: rect.width, height: rect.height,
      textStart: rect.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft), dpr: devicePixelRatio };
  }));
  await testInfo.attach('全部输入起点', { body: JSON.stringify(measurements), contentType: 'application/json' });
  await page.screenshot({ path: testInfo.outputPath('贴图资源与真实预览.png') });
});

test('原生选择损坏PNG保留旧资源，导入缺失主体并重做', async ({ desktopHost }) => {
  const { page, projectPath, temporary, pid } = desktopHost;
  const source = join(temporary, '损坏.png');
  await writeFile(source, 'fake PNG');
  const target = join(projectPath, 'sprites/units/twin.png');
  const original = await readFile(target);
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree'); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const resources = page.getByRole('region', { name: '贴图资源', exact: true });
  const main = resources.locator('[data-sprite-suffix=""]');
  const select = () => execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    resolve(import.meta.dirname, 'folder-dialog.ps1'), '-TestProcessId', String(pid), '-DialogName', '打开',
    '-Action', 'select', '-ProjectPath', source], { windowsHide: true, timeout: 20_000 });
  await main.getByRole('button', { name: /替换.*贴图/ }).click();
  await main.getByRole('button', { name: '选择并替换' }).click(); select();
  await expect(resources.getByRole('alert')).toContainText('PNG');
  expect(await readFile(target)).toEqual(original);
  await main.getByRole('button', { name: '取消', exact: true }).click();
  await rm(target);
  await expect(main.getByRole('button', { name: /导入.*贴图/ })).toBeEnabled();
  await writeFile(source, original);
  await main.getByRole('button', { name: /导入.*贴图/ }).click(); select();
  await expect.poll(() => readFile(target).catch(() => null)).toEqual(original);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(main.getByRole('button', { name: /导入.*贴图/ })).toBeEnabled();
  await page.getByRole('button', { name: '重做', exact: true }).click();
  await expect.poll(() => readFile(target).catch(() => null)).toEqual(original);
});
