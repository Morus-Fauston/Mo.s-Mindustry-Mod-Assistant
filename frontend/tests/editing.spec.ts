import { test, expect } from './desktop-fixture';
import { readFile, writeFile, rename, mkdir, rmdir } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import type { Page } from '@playwright/test';

async function openUnit(page: Page, projectPath: string) {
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree');
  await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await page.locator('[data-path="content/units/twin.json"]').click();
  const input = page.getByRole('tabpanel', { name: 'content/units/twin.json' }).getByRole('textbox');
  await expect(input).toHaveValue('137');
  return input;
}

test('生命值编辑撤销保存重开与同名文件隔离', async ({ desktopHost }, testInfo) => {
  const { page, projectPath } = desktopHost;
  const input = await openUnit(page, projectPath);
  await page.locator('[data-path="content/blocks/twin.json"]').click();
  await expect(page.getByRole('tabpanel', { name: 'content/blocks/twin.json' })).toBeVisible();
  await page.getByRole('tab', { name: 'twin', exact: true }).first().click();
  await input.fill('250');
  await input.press('Enter');
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(input).toHaveValue('137');
  await page.getByRole('button', { name: '重做', exact: true }).click();
  await expect(input).toHaveValue('250');
  // The save scope is all opened documents, including the same-named block.
  await writeFile(join(projectPath, 'content/blocks/twin.json'), JSON.stringify({ type: 'Wall', health: 999 }));
  await input.press('Control+s');
  await expect(page.getByRole('status')).toContainText('已保存所有打开的内容');
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/twin.json'), 'utf8')).health).toBe(250);
  expect(JSON.parse(await readFile(join(projectPath, 'content/blocks/twin.json'), 'utf8')).health).toBe(823);
  const measurements = await page.locator('input,textarea,select').evaluateAll(elements => elements.map(element => {
    const style = getComputedStyle(element), bounds = element.getBoundingClientRect();
    return { label: element.getAttribute('aria-label'), width: bounds.width, height: bounds.height,
      textStart: bounds.x + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft), dpr: devicePixelRatio };
  }));
  await testInfo.attach('全部输入文本起点', { body: JSON.stringify(measurements, null, 2), contentType: 'application/json' });
  await writeFile(testInfo.outputPath('全部输入起点.json'), JSON.stringify(measurements, null, 2));
  await page.screenshot({ path: testInfo.outputPath('生命值编辑.png') });
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await expect(page.getByRole('tab')).toHaveCount(0);
  await page.locator('[data-path="content/units/twin.json"]').click();
  await expect(input).toHaveValue('250');
});

test('关闭全部拒绝迟发读取，负值保持错误标记且不落盘', async ({ desktopHost }) => {
  const { page, projectPath } = desktopHost;
  const input = await openUnit(page, projectPath);
  await input.fill('-1'); await input.press('Enter');
  await expect(input).toHaveAttribute('aria-invalid', 'true');
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/twin.json'), 'utf8')).health).toBe(137);
  await input.press('Escape');
  await expect(input).toHaveValue('137');
  await page.evaluate(() => {
    const host = window as any, original = host.pywebview.api.request;
    host.pywebview.api.request = async (envelope: any) => {
      if (envelope.action === 'read_document') {
        host.pywebview.api.request = original;
        host.readHeld = true;
        await new Promise<void>(resolve => { host.releaseLateRead = resolve; });
        const result = await original(envelope);
        host.lateReadResult = result;
        return result;
      }
      return original(envelope);
    };
  });
  await page.locator('[data-path="content/blocks/twin.json"]').click();
  await expect.poll(() => page.evaluate(() => (window as any).readHeld)).toBe(true);
  await page.getByRole('button', { name: '关闭全部', exact: true }).click();
  await expect(page.getByRole('tab')).toHaveCount(0);
  await page.evaluate(() => (window as any).releaseLateRead());
  await expect.poll(() => page.evaluate(() => (window as any).lateReadResult?.error?.code)).toBe('STALE_REVISION');
  await page.locator('[data-path="content/units/twin.json"]').click();
  await expect(input).toHaveValue('137');
  await expect(page.getByRole('tab')).toHaveCount(1);
});

test('真实保存失败保留修改及关闭裁决', async ({ desktopHost }, testInfo) => {
  const { page, projectPath } = desktopHost;
  const input = await openUnit(page, projectPath);
  await input.fill('333'); await input.press('Enter');
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeEnabled();
  const file = join(projectPath, 'content/units/twin.json');
  await rename(file, `${file}.backup`); await mkdir(file);
  await page.getByRole('button', { name: '关闭 content/units/twin.json', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: '保存并继续' }).click();
  await expect(dialog.getByRole('alert')).toBeVisible();
  await expect(input).toHaveValue('333');
  await page.screenshot({ path: testInfo.outputPath('保存失败不关闭.png') });
  await dialog.getByRole('button', { name: '取消', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('tab')).toHaveCount(1);
  await rmdir(file); await rename(`${file}.backup`, file);
  await page.getByRole('button', { name: '保存已打开内容' }).click();
  await expect(page.getByRole('status')).toContainText('已保存所有打开的内容');
  expect(JSON.parse(await readFile(file, 'utf8')).health).toBe(333);
});

test('原生关闭先取消，保存失败留窗，修复后保存退出', async ({ desktopHost }, testInfo) => {
  const { page, projectPath, pid } = desktopHost;
  const input = await openUnit(page, projectPath);
  await input.fill('420'); await input.press('Enter');
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeEnabled();
  const close = () => execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    resolve(import.meta.dirname, 'window-close.ps1'), '-TestProcessId', String(pid)], { windowsHide: true, timeout: 10_000 });
  close();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('关闭工作台');
  await dialog.getByRole('button', { name: '取消', exact: true }).click();
  await expect(input).toHaveValue('420');
  const file = join(projectPath, 'content/units/twin.json');
  await rename(file, `${file}.backup`); await mkdir(file);
  close();
  await dialog.getByRole('button', { name: '保存并继续' }).click();
  await expect(dialog.getByRole('alert')).toBeVisible();
  expect(page.isClosed()).toBe(false);
  await page.screenshot({ path: testInfo.outputPath('原生关闭保存失败.png') });
  await rmdir(file); await rename(`${file}.backup`, file);
  const closed = page.waitForEvent('close');
  await dialog.getByRole('button', { name: '保存并继续' }).click();
  await closed;
  expect(JSON.parse(await readFile(file, 'utf8')).health).toBe(420);
});

test('编辑响应超时查询原结果，放弃关闭可从会话历史恢复', async ({ desktopHost }) => {
  const { page, projectPath } = desktopHost;
  const input = await openUnit(page, projectPath);
  await page.evaluate(() => {
    const host = window as any, original = host.pywebview.api.request;
    host.editCount = 0;
    host.pywebview.api.request = async (envelope: any) => {
      if (envelope.action === 'set_field') {
        host.editCount += 1;
        const result = await original(envelope);
        return new Promise(resolve => { host.releaseEdit = () => resolve(result); });
      }
      return original(envelope);
    };
  });
  await input.fill('777'); await input.press('Enter');
  await page.getByRole('button', { name: '查询操作结果' }).click({ timeout: 22_000 });
  await expect(page.getByRole('status')).toContainText('已取得原操作结果');
  expect(await page.evaluate(() => (window as any).editCount)).toBe(1);
  await page.evaluate(() => (window as any).releaseEdit());
  await page.getByRole('button', { name: '关闭 content/units/twin.json', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: '放弃修改' }).click();
  await expect(page.getByRole('tab')).toHaveCount(0);
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/twin.json'), 'utf8')).health).toBe(137);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(input).toHaveValue('777');
  await page.getByRole('button', { name: '保存已打开内容' }).click();
  await expect(page.getByRole('status')).toContainText('已保存所有打开的内容');
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/twin.json'), 'utf8')).health).toBe(777);
});

test('脏工程切换先裁决，取消原生选择保留当前修改', async ({ desktopHost }) => {
  const { page, projectPath, pid } = desktopHost;
  const input = await openUnit(page, projectPath);
  await input.fill('666'); await input.press('Enter');
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: '打开工程', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
  await expect(input).toHaveValue('666');
  await page.getByRole('button', { name: '打开工程', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: '放弃修改' }).click();
  execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    resolve(import.meta.dirname, 'folder-dialog.ps1'), '-TestProcessId', String(pid), '-Action', 'cancel', '-ProjectPath', projectPath],
    { windowsHide: true, timeout: 20_000 });
  await expect(page.getByRole('status')).toContainText('已取消打开工程');
  await expect(input).toHaveValue('666');
  await expect(page.getByRole('tab').getByLabel('未保存')).toBeVisible();
});
