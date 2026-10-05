import { test, expect } from './desktop-fixture';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

async function openSource(host: { page: import('@playwright/test').Page; projectPath: string }, path = 'content/units/twin.json') {
  const { page, projectPath } = host;
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree'); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator(`[data-path="${path}"]`).click();
  const panel = page.getByRole('tabpanel', { name: path });
  await expect(panel).toBeVisible();
  if (!path.endsWith('broken.json')) await panel.getByRole('button', { name: 'JSON 源码', exact: true }).click();
  const source = panel.locator('.cm-content'); await expect(source).toBeVisible();
  return { page, panel, source, tree, file: join(projectPath, path) };
}

test('源码与表单双向共享撤销保留未知字段及大整数', async ({ desktopHost }, info) => {
  const { page, panel, source, file } = await openSource(desktopHost);
  await source.fill('{"type":"flying","health":246,"unknown":{"整数":9007199254740993123}}');
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeEnabled();
  await expect(source).toBeFocused(); // 500ms 自动应用，无失焦提交。
  await panel.getByRole('button', { name: '表单', exact: true }).click();
  const folds = panel.locator('button[aria-label^="展开"]:not(:disabled)');
  while (await folds.count()) await folds.first().click();
  const health = panel.locator('[data-field="health"] input').first();
  await expect(health).toHaveValue('246');
  await health.fill('357'); await health.press('Enter');
  await panel.getByRole('button', { name: 'JSON 源码', exact: true }).click();
  await expect(source).toContainText('357');
  await source.press('Control+z'); await expect(source).toContainText('246');
  await source.press('Control+z'); await expect(source).toContainText('137');
  await source.press('Control+y'); await expect(source).toContainText('246');
  await source.press('Control+y'); await expect(source).toContainText('357');
  await panel.getByRole('button', { name: '格式化', exact: true }).click();
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(() => readFile(file, 'utf8')).toContain('9007199254740993123');
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).health).toBe(357);
  await panel.getByRole('button', { name: '查找与替换', exact: true }).click();
  await expect(panel.locator('.cm-search')).toBeVisible();
  await panel.locator('.cm-search input[name="search"]').fill('unknown');
  const measurements = await page.locator('input,textarea,select,[contenteditable="true"]').evaluateAll(elements => elements.map(element => {
    const textBox = element.matches('[contenteditable]') ? element.querySelector('.cm-line') ?? element : element;
    const rect = textBox.getBoundingClientRect(), css = getComputedStyle(textBox);
    return { label: element.getAttribute('aria-label') ?? element.getAttribute('name'), field: element.closest('[data-field]')?.getAttribute('data-field'),
      tag: element.tagName, width: rect.width, textStart: rect.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft), inset: parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft) };
  }));
  await writeFile(info.outputPath('源码与查找全部输入起点.json'), JSON.stringify(measurements, null, 2));
  expect(measurements.filter(item => item.width > 0).every(item => Number.isFinite(item.textStart))).toBe(true);
  await page.screenshot({ path: info.outputPath('源码与中文查找.png') });
});

test('非法源码保留只读旧表单保存失败关闭可取消与放弃', async ({ desktopHost }, info) => {
  const { page, panel, source, tree, file } = await openSource(desktopHost);
  const original = await readFile(file, 'utf8');
  await source.fill('{"health":');
  await expect(source).toHaveAttribute('aria-invalid', 'true');
  await panel.getByRole('button', { name: '表单', exact: true }).click();
  await expect(panel.getByText('源码输入尚未应用，以下显示上一次有效内容，暂不可编辑。')).toBeVisible();
  await expect(panel.locator('[data-field="health"] input').first()).toBeDisabled();
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  expect(await readFile(file, 'utf8')).toBe(original);
  await tree.locator('[data-path="content/blocks/twin.json"]').click();
  await page.getByRole('tab').filter({ hasText: 'twin' }).first().click();
  await panel.getByRole('button', { name: 'JSON 源码', exact: true }).click();
  await expect(source).toHaveText('{"health":');
  await page.getByRole('button', { name: '关闭 content/units/twin.json', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: '取消', exact: true }).click();
  await expect(source).toHaveText('{"health":');
  await page.screenshot({ path: info.outputPath('非法源码留存.png') });
  await page.getByRole('button', { name: '关闭 content/units/twin.json', exact: true }).click();
  await dialog.getByRole('button', { name: /放弃/ }).click();
  await expect(panel).toHaveCount(0);
  expect(await readFile(file, 'utf8')).toBe(original);
});

test('首次坏JSON不失焦自动修复保存后撤销回原始状态', async ({ desktopHost }, info) => {
  const { page, panel, source, file } = await openSource(desktopHost, 'content/units/broken.json');
  await expect(source).toHaveText('{invalid');
  await expect(source).toHaveAttribute('aria-invalid', 'true');
  await source.fill('{"type":"flying","health":482}');
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeEnabled();
  await expect(source).toBeFocused();
  await expect(panel.getByRole('button', { name: '放弃源码输入', exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => { try { return JSON.parse(await readFile(file, 'utf8')).health; } catch { return null; } }).toBe(482);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(source).toHaveText('{invalid');
  await expect(source).toHaveAttribute('aria-invalid', 'true');
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  expect(JSON.parse(await readFile(file, 'utf8')).health).toBe(482);
  await panel.getByRole('button', { name: '表单', exact: true }).click();
  await expect(panel.getByText('源码无法解析，尚无可用表单。请切换到 JSON 源码修复。')).toBeVisible();
  await expect(panel.locator('[data-group]')).toHaveCount(0);
  await page.screenshot({ path: info.outputPath('撤销回首次坏JSON.png') });
  await page.getByRole('button', { name: '重做', exact: true }).click();
  await expect(panel.locator('[data-group]')).not.toHaveCount(0);
});

test('源码组合输入边界及迟到格式化隔离', async ({ desktopHost }) => {
  const { page, panel, source, file } = await openSource(desktopHost);
  await source.dispatchEvent('compositionstart', { data: '' });
  await source.fill('{"type":"flying","health":582,"description":"中文组合"}');
  await page.waitForTimeout(650); // 明确验证500ms窗口内组合输入不能提交。
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeDisabled();
  await source.dispatchEvent('compositionend', { data: '中文组合' });
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeEnabled();
  await page.evaluate(() => {
    const host = window as unknown as { pywebview: { api: { request: (envelope: any) => Promise<any> } }; releaseFormat?: () => void; formatCompleted?: boolean };
    const original = host.pywebview.api.request;
    host.pywebview.api.request = async envelope => {
      const result = await original(envelope);
      if (envelope.action === 'format_source') {
        host.pywebview.api.request = original; host.formatCompleted = true;
        return new Promise(resolve => { host.releaseFormat = () => resolve(result); });
      }
      return result;
    };
  });
  await panel.getByRole('button', { name: '格式化', exact: true }).click();
  await expect.poll(() => page.evaluate(() => (window as any).formatCompleted)).toBe(true);
  await source.fill('{"type":"flying","health":693}');
  await expect(panel.getByRole('button', { name: '放弃源码输入', exact: true })).toHaveCount(0);
  await page.evaluate(() => (window as any).releaseFormat());
  await page.getByRole('button', { name: '保存已打开内容', exact: true }).click();
  await expect.poll(async () => JSON.parse(await readFile(file, 'utf8')).health).toBe(693);
  await expect(source).not.toContainText('582');
});
