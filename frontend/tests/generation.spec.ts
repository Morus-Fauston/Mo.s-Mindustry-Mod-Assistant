import { test, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';

test('真实生成预览取消覆盖整批撤销和输出像素', async ({ desktopHost }, info) => {
  const { page, projectPath } = desktopHost;
  execFileSync(resolve(import.meta.dirname, '../../.venv-web/Scripts/python.exe'), ['-c',
    "from PIL import Image; import sys; im=Image.new('RGBA',(7,7)); im.putpixel((3,3),(200,50,30,255)); im.save(sys.argv[1])",
    join(projectPath, 'sprites/units/twin.png')], { windowsHide: true });
  await writeFile(join(projectPath, 'content/units/twin.json'), '{"type":"flying","health":100}');
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true }); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const generator = page.getByRole('region', { name: '贴图生成', exact: true });
  await expect(generator.getByRole('button', { name: '预览生成结果' })).toBeEnabled();
  for (const name of ['完整图', '轮廓', '阴影']) await generator.getByRole('checkbox', { name, exact: true }).check();
  const width = generator.getByRole('textbox', { name: '描边宽度', exact: true });
  await width.fill('1.5');
  await generator.getByRole('button', { name: '预览生成结果' }).click();
  await expect(width).toHaveAttribute('aria-invalid', 'true');
  await width.fill('1');
  await generator.getByRole('textbox', { name: '描边颜色', exact: true }).fill('#000000');
  await generator.getByRole('textbox', { name: '阴影透明度', exact: true }).fill('80');
  const measurements = await page.locator('input,textarea,select,[contenteditable="true"]').evaluateAll(elements => elements.map(element => {
    const r = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { label: element.getAttribute('aria-label'), width: r.width, textStart: r.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft) };
  }));
  expect(measurements.filter(row => row.width > 0).every(row => Number.isFinite(row.textStart))).toBe(true);
  await info.attach('全部输入起点', { body: JSON.stringify(measurements), contentType: 'application/json' });
  const paths = ['-full', '-outline', '-shadow'].map(suffix => join(projectPath, `sprites/units/twin${suffix}.png`));
  await generator.getByRole('button', { name: '预览生成结果' }).click();
  await expect(generator.locator('img')).toHaveCount(3);
  for (const path of paths) expect(await readFile(path).catch(() => null)).toBeNull();
  const candidate = await generator.locator('img').evaluateAll(images => images.map(image => image.getAttribute('src')!));
  await generator.getByRole('button', { name: '取消预览' }).press('Escape');
  await expect(generator.locator('img')).toHaveCount(0);
  await expect(generator.getByRole('button', { name: '预览生成结果' })).toBeFocused();
  await generator.getByRole('button', { name: '预览生成结果' }).click();
  await expect(generator.locator('img')).toHaveCount(3);
  await generator.getByRole('button', { name: '确认写入工程' }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath('真实生成候选.png') });
  await generator.getByRole('button', { name: '确认写入工程' }).click();
  for (let index = 0; index < paths.length; index++) {
    const expected = Buffer.from(candidate[index].split(',')[1], 'base64');
    await expect.poll(() => readFile(paths[index]).catch(() => null)).toEqual(expected);
  }
  const bytes = await Promise.all(paths.map(path => readFile(path)));
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  for (const path of paths) await expect.poll(() => readFile(path).catch(() => null)).toBeNull();
  await page.getByRole('button', { name: '重做', exact: true }).click();
  for (let i = 0; i < paths.length; i++) await expect.poll(() => readFile(paths[i]).catch(() => null)).toEqual(bytes[i]);
  await expect(generator.getByRole('button', { name: '预览生成结果' })).toBeEnabled();
  await generator.getByRole('button', { name: '预览生成结果' }).click();
  await expect(generator.getByRole('button', { name: '确认覆盖并写入' })).toBeDisabled();
  await generator.getByRole('checkbox', { name: '我确认覆盖以上标记为已有的贴图' }).check();
  await expect(generator.getByRole('button', { name: '确认覆盖并写入' })).toBeEnabled();
  await generator.getByRole('button', { name: '取消预览' }).click();
  await tree.locator('[data-path="content/blocks/twin.json"]').click();
  await expect(generator).toContainText('当前内容没有可生成的贴图类型');
});

test('生成桥接超时查询原请求并释放迟到候选', async ({ desktopHost }, info) => {
  const { page, projectPath } = desktopHost;
  await page.evaluate(() => {
    const host = window as any, request = host.pywebview.api.request;
    host.generationCalls = []; host.delayGeneration = 'preview_generation';
    host.pywebview.api.request = async (envelope: any) => {
      host.generationCalls.push({ action: envelope.action, id: envelope.requestId });
      const response = await request(envelope);
      if (envelope.action === host.delayGeneration && response.ok) {
        host.delayGeneration = null;
        // Real backend commits once; simulate a lost delivery, not business data.
        await new Promise(resolve => setTimeout(resolve, 17_000));
      }
      return response;
    };
  });
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true }); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const generator = page.getByRole('region', { name: '贴图生成', exact: true });
  await generator.getByRole('button', { name: '预览生成结果' }).click();
  const recover = page.getByRole('button', { name: '查询操作结果' });
  await expect(recover).toBeVisible({ timeout: 20_000 });
  await recover.click();
  await expect(page.getByText('已取回并释放原预览，请重新预览。', { exact: true })).toBeVisible();
  await expect(generator.locator('img')).toHaveCount(0);
  await expect.poll(() => page.evaluate(() => (window as any).generationCalls.filter((row: any) => row.action === 'cancel_generation').length)).toBe(1);
  expect(await page.evaluate(() => (window as any).generationCalls.filter((row: any) => row.action === 'preview_generation').length)).toBe(1);
  await generator.getByRole('button', { name: '预览生成结果' }).click();
  await expect(generator.locator('img')).toHaveCount(1);
  await page.evaluate(() => { (window as any).delayGeneration = 'confirm_generation'; });
  await generator.getByRole('button', { name: '确认写入工程' }).click();
  await expect(recover).toBeVisible({ timeout: 20_000 });
  await recover.click();
  await expect(page.getByText('贴图已写入工程，可通过撤销恢复。', { exact: true }).first()).toBeVisible();
  expect(await readFile(join(projectPath, 'sprites/units/twin-full.png'))).toBeTruthy();
  expect(await page.evaluate(() => (window as any).generationCalls.filter((row: any) => row.action === 'confirm_generation').length)).toBe(1);
  await expect(generator.locator('img')).toHaveCount(0);
  await info.attach('真实生成请求次数', { body: JSON.stringify(await page.evaluate(() => (window as any).generationCalls)), contentType: 'application/json' });
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect.poll(() => readFile(join(projectPath, 'sprites/units/twin-full.png')).catch(() => null)).toBeNull();
});
