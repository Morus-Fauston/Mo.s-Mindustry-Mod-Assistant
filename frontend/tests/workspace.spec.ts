import { test, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { rm } from 'node:fs/promises';

test('真实工程树的同名内容、搜索、键盘与标签', async ({ desktopHost }, testInfo) => {
  const { page, projectPath } = desktopHost;
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree');
  await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) {
    await tree.locator('[aria-expanded="false"]').first().click();
  }
  // File identity, rather than display text, distinguishes the two twin files.
  const unitNode = page.locator('[data-path="content/units/twin.json"]');
  const blockNode = page.locator('[data-path="content/blocks/twin.json"]');
  await unitNode.click();
  await expect(page.getByRole('tabpanel', { name: 'content/units/twin.json' }).getByRole('textbox')).toHaveValue('137');
  const unitPage = page.getByRole('tabpanel', { name: 'content/units/twin.json' });
  await unitPage.evaluate(element => { element.scrollTop = 137; });
  const scrollTop = await unitPage.evaluate(element => element.scrollTop);
  expect(scrollTop).toBeGreaterThan(136);
  await blockNode.click();
  await expect(page.getByRole('tabpanel', { name: 'content/blocks/twin.json' })).toContainText('823');
  await unitNode.click();
  await expect(page.getByRole('tab')).toHaveCount(2);
  await expect(page.getByRole('tabpanel', { name: 'content/units/twin.json' })).toBeVisible();
  await expect.poll(() => unitPage.evaluate(element => element.scrollTop)).toBe(scrollTop);
  await unitPage.evaluate(element => { element.scrollTop = 0; });
  const search = page.getByRole('textbox', { name: '搜索文件' });
  const weapons = tree.locator('[data-node-id="content/weapons"]');
  await weapons.click();
  await expect(tree.locator('[data-path="content/weapons/laser.json"]')).toHaveCount(0);
  await search.fill('激光武器');
  await expect(tree.locator('[data-path="content/weapons/laser.json"]')).toBeVisible();
  await page.getByRole('button', { name: '清空搜索' }).click();
  await expect(search).toBeFocused();
  await expect(weapons).toHaveAttribute('aria-expanded', 'false');
  await expect(tree.locator('[data-path="content/weapons/laser.json"]')).toHaveCount(0);
  await search.fill('同名单元');
  await expect(unitNode).toBeVisible();
  await expect(blockNode).toHaveCount(0);
  await search.press('Escape');
  await expect(search).toHaveValue('');
  await expect(search).toBeFocused();
  await expect(blockNode).toBeVisible();
  await unitNode.focus();
  await unitNode.press('Home');
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowDown');
  await expect(tree.locator(':focus')).toHaveCount(1);
  await page.getByRole('button', { name: '关闭其他', exact: true }).click();
  await expect(page.getByRole('tab')).toHaveCount(1);
  await page.locator('[data-path="content/units/broken.json"]').click();
  await expect(page.getByRole('alert')).toContainText('broken.json');
  await expect(page.getByRole('tabpanel', { name: 'content/units/twin.json' }).getByRole('textbox')).toHaveValue('137');
  const measurements = await page.locator('input,textarea,select').evaluateAll(controls => controls.map(element => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return { label: element.getAttribute('aria-label'), width: rect.width, height: rect.height,
      textStart: rect.x + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
      viewport: { width: innerWidth, height: innerHeight, dpr: devicePixelRatio } };
  }));
  await testInfo.attach('全部输入起点', { body: JSON.stringify(measurements, null, 2), contentType: 'application/json' });
  await page.screenshot({ path: testInfo.outputPath('工程树与标签.png') });
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await expect(page.getByRole('tab')).toHaveCount(0);
  await expect(tree).toBeVisible();
});

test('原生目录选择支持取消与中文空格路径', async ({ desktopHost }, testInfo) => {
  const { page, projectPath, pid } = desktopHost;
  const runDialog = (action: string) => execFileSync('powershell.exe', [
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', resolve(import.meta.dirname, 'folder-dialog.ps1'),
    '-TestProcessId', String(pid), '-Action', action, '-ProjectPath', projectPath,
  ], { windowsHide: true, encoding: 'utf8', timeout: 20_000 });
  await page.getByRole('button', { name: '打开工程', exact: true }).click();
  let cancelled: string;
  try { cancelled = runDialog('cancel'); }
  catch (error) {
    await testInfo.attach('对话框失败时界面', { body: await page.locator('body').innerText(), contentType: 'text/plain' });
    await testInfo.attach('原生窗口枚举', { body: String((error as { stdout?: string }).stdout ?? ''), contentType: 'text/plain' });
    throw error;
  }
  await expect(page.getByRole('status')).toContainText('已取消打开工程');
  await expect(page.getByRole('tree')).toHaveCount(0);
  await page.getByRole('button', { name: '打开工程', exact: true }).click();
  let opened: string;
  try { opened = runDialog('select'); }
  catch (error) {
    await testInfo.attach('目录输入框枚举', { body: String((error as { stdout?: string }).stdout ?? ''), contentType: 'text/plain' });
    throw error;
  }
  await expect(page.getByRole('tree')).toBeVisible();
  await expect(page.getByRole('status')).toContainText('已打开 真实验收工程');
  await testInfo.attach('原生目录选择', { body: cancelled + opened, contentType: 'text/plain' });
  await page.screenshot({ path: testInfo.outputPath('原生选择后.png') });
});

test('打开响应超时后查询原结果，关闭全部隔离迟到读取', async ({ desktopHost }) => {
  const { page, projectPath } = desktopHost;
  // Hold a real completed backend response at the transport boundary.
  // The backend still opens the actual disk project and issues the session ID.
  await page.evaluate(() => {
    const host = window as unknown as { pywebview: { api: { request: (envelope: any) => Promise<any> } }; releaseOpen?: () => void; openCompleted?: boolean };
    const original = host.pywebview.api.request;
    host.pywebview.api.request = async envelope => {
      const result = await original(envelope);
      if (envelope.action === 'open_project') {
        host.pywebview.api.request = original;
        host.openCompleted = true;
        return new Promise(resolve => { host.releaseOpen = () => resolve(result); });
      }
      return result;
    };
  });
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  await expect.poll(() => page.evaluate(() => (window as any).openCompleted)).toBe(true);
  await page.getByRole('button', { name: '查询打开结果' }).click({ timeout: 22_000 });
  await expect(page.getByRole('tree')).toBeVisible();
  await page.evaluate(() => (window as any).releaseOpen());
  const tree = page.getByRole('tree');
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await page.locator('[data-path="content/units/twin.json"]').click();
  await expect(page.getByRole('tab')).toHaveCount(1);
  await page.evaluate(() => {
    const host = window as any;
    const original = host.pywebview.api.request;
    host.pywebview.api.request = async (envelope: any) => {
      const result = await original(envelope);
      if (envelope.action === 'read_document') {
        host.pywebview.api.request = original;
        host.readCompleted = true;
        return new Promise(resolve => { host.releaseRead = () => resolve(result); });
      }
      return result;
    };
  });
  await page.locator('[data-path="content/blocks/twin.json"]').click();
  await expect.poll(() => page.evaluate(() => (window as any).readCompleted)).toBe(true);
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await page.evaluate(() => (window as any).releaseRead());
  await expect(page.getByRole('tab')).toHaveCount(0);
  await page.locator('[data-path="content/units/twin.json"]').click();
  await expect(page.getByRole('tabpanel', { name: 'content/units/twin.json' }).getByRole('textbox')).toHaveValue('137');
  await expect(page.getByRole('tab')).toHaveCount(1);
});

test('最近工程路径失效时反馈错误且不显示假工程', async ({ desktopHost }) => {
  const { page, projectPath } = desktopHost;
  const recent = page.getByRole('button').filter({ hasText: projectPath });
  await expect(recent).toBeVisible();
  await rm(resolve(projectPath, 'mod.json'));
  await recent.click();
  await expect(page.getByRole('alert')).toContainText('无法打开工程');
  await expect(page.getByRole('tree')).toHaveCount(0);
});
