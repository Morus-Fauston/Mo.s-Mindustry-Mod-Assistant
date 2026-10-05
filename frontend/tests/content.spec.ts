import { test, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { readFile, stat, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import type { Page, TestInfo } from '@playwright/test';

async function measure(page: Page, info: TestInfo, name: string) {
  const rows = await page.locator('input,textarea,select,[contenteditable="true"]').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { tag: element.tagName, id: element.id, width: rect.width, visible: rect.width > 0 && rect.height > 0,
      textStart: rect.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft),
      right: rect.right, viewport: innerWidth };
  }));
  expect(rows.filter(row => row.visible).every(row => Number.isFinite(row.textStart) && row.right <= row.viewport)).toBe(true);
  await info.attach(name, { body: JSON.stringify(rows), contentType: 'application/json' });
}

async function expand(page: Page) {
  const tree = page.getByRole('tree', { name: '工程文件', exact: true });
  await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  return tree;
}

test('内容操作真实重命名删除与跨类别撤销保留文件标签', async ({ desktopHost }, info) => {
  const { page, projectPath } = desktopHost;
  const original = await readFile(join(projectPath, 'content/units/twin.json'));
  const other = await readFile(join(projectPath, 'content/blocks/twin.json'));
  const sprite = await readFile(join(projectPath, 'sprites/units/twin.png'));
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = await expand(page);
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const panel = page.getByRole('tabpanel', { name: 'content/units/twin.json', exact: true });
  await panel.getByRole('textbox', { name: '生命值', exact: true }).fill('239');
  await panel.getByRole('textbox', { name: '生命值', exact: true }).press('Tab');
  await page.getByRole('button', { name: '重命名', exact: true }).click();
  let dialog = page.getByRole('dialog', { name: '重命名内容', exact: true });
  await dialog.getByRole('textbox', { name: '新名称', exact: true }).fill('moved');
  await measure(page, info, '重命名全部输入文本起点');
  await dialog.getByRole('button', { name: '确认重命名', exact: true }).click();
  const choice = page.getByRole('dialog', { name: '继续内容操作', exact: true });
  await choice.getByRole('button', { name: '取消', exact: true }).click();
  await expect(dialog).toContainText('已取消操作');
  expect(await readFile(join(projectPath, 'content/units/twin.json'))).toEqual(original);
  await dialog.getByRole('button', { name: '确认重命名', exact: true }).click();
  await choice.getByRole('button', { name: '保存并继续', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('tabpanel', { name: 'content/units/moved.json', exact: true })).toBeVisible();
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/moved.json'), 'utf8')).health).toBe(239);
  expect(await readFile(join(projectPath, 'sprites/units/moved.png'))).toEqual(sprite);
  expect(await readFile(join(projectPath, 'content/blocks/twin.json'))).toEqual(other);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(panel).toBeVisible();
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/twin.json'), 'utf8')).health).toBe(239);
  await page.getByRole('button', { name: '重做', exact: true }).click();
  await expect(page.getByRole('tabpanel', { name: 'content/units/moved.json', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '删除内容', exact: true }).click();
  dialog = page.getByRole('dialog', { name: '删除内容', exact: true });
  await dialog.getByRole('button', { name: '确认删除内容', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(await stat(join(projectPath, 'content/units/moved.json')).catch(() => null)).toBeNull();
  expect(await readFile(join(projectPath, 'sprites/units/moved.png'))).toEqual(sprite);
  await expect(page.getByRole('tab')).toHaveCount(0);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(page.getByRole('tabpanel', { name: 'content/units/moved.json', exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('内容撤销后的工作台.png') });
});

test('内容真实模板新建覆盖坏源码及撤销恢复', async ({ desktopHost }, info) => {
  const { page, projectPath } = desktopHost;
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = await expand(page);
  await tree.locator('[data-path="content/units/broken.json"]').click();
  await page.getByRole('button', { name: '新建内容', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '新建内容', exact: true });
  await dialog.getByRole('combobox', { name: '内容类别', exact: true }).selectOption('units');
  await dialog.getByRole('combobox', { name: '内容模板', exact: true }).selectOption('UnitType-flying');
  await dialog.getByRole('textbox', { name: '内容名称', exact: true }).fill('broken');
  await measure(page, info, '新建内容全部输入文本起点');
  await dialog.getByRole('button', { name: '创建内容', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '确认覆盖此文件', exact: true })).toBeVisible();
  expect(await readFile(join(projectPath, 'content/units/broken.json'), 'utf8')).toBe('{invalid');
  await dialog.getByRole('button', { name: '确认覆盖此文件', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/broken.json'), 'utf8')).type).toBe('flying');
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(page.getByRole('tabpanel', { name: 'content/units/broken.json', exact: true }).locator('.cm-content')).toHaveText('{invalid');
  expect(await readFile(join(projectPath, 'content/units/broken.json'), 'utf8')).toBe('{invalid');
  await page.getByRole('button', { name: '重做', exact: true }).click();
  await expect.poll(() => readFile(join(projectPath, 'content/units/broken.json'), 'utf8')).toContain('"flying"');
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/broken.json'), 'utf8')).type).toBe('flying');
});

test('新建工程原生取消与同一命令栈跨空工作台重做', async ({ desktopHost }, info) => {
  const { page, temporary, pid } = desktopHost;
  const native = (action: string) => execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', resolve(import.meta.dirname, 'folder-dialog.ps1'), '-TestProcessId', String(pid), '-Action', action,
    '-ProjectPath', temporary], { windowsHide: true, encoding: 'utf8', timeout: 20_000 });
  const create = async () => {
    await page.getByRole('button', { name: '新建工程', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '新建工程', exact: true });
    await dialog.getByRole('textbox', { name: '模组 ID', exact: true }).fill('new-project');
    await dialog.getByRole('textbox', { name: '显示名称', exact: true }).fill('新建真实工程');
    await dialog.getByRole('textbox', { name: '作者', exact: true }).fill('验收');
    await measure(page, info, '新建工程全部输入文本起点');
    await dialog.getByRole('button', { name: '选择父目录并创建', exact: true }).click();
  };
  await create();
  await info.attach('取消父目录', { body: native('cancel'), contentType: 'text/plain' });
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(await stat(join(temporary, 'new-project')).catch(() => null)).toBeNull();
  await create();
  await info.attach('选择父目录', { body: native('select'), contentType: 'text/plain' });
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('tree', { name: '工程文件', exact: true })).toBeVisible();
  expect(JSON.parse(await readFile(join(temporary, 'new-project/mod.json'), 'utf8')).displayName).toBe('新建真实工程');
  await page.getByRole('button', { name: '新建内容', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '新建内容', exact: true });
  await dialog.getByRole('textbox', { name: '内容名称', exact: true }).fill('first');
  await dialog.getByRole('button', { name: '创建内容', exact: true }).click();
  await expect(page.getByRole('tabpanel', { name: 'content/units/first.json', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(page.getByRole('tab')).toHaveCount(0);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(page.getByRole('tree', { name: '工程文件', exact: true })).toHaveCount(0);
  expect(await stat(join(temporary, 'new-project')).catch(() => null)).toBeNull();
  await expect(page.getByRole('button', { name: '新建内容', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '重做', exact: true }).click();
  await expect(page.getByRole('tree', { name: '工程文件', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '重做', exact: true }).click();
  await expect(page.getByRole('tabpanel', { name: 'content/units/first.json', exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('新建工程与内容双重做.png') });
});

test('内容重命名超时弹窗只查询原结果', async ({ desktopHost }) => {
  const { page, projectPath } = desktopHost;
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = await expand(page); await tree.locator('[data-path="content/units/twin.json"]').click();
  await page.evaluate(() => {
    const host = window as any, original = host.pywebview.api.request;
    host.contentRequests = [];
    host.pywebview.api.request = async (envelope: any) => {
      host.contentRequests.push(envelope.action);
      const response = await original(envelope);
      if (envelope.action === 'rename_content' && response.ok) await new Promise(resolve => setTimeout(resolve, 17_000));
      return response;
    };
  });
  await page.getByRole('button', { name: '重命名', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '重命名内容', exact: true });
  await dialog.getByRole('textbox', { name: '新名称', exact: true }).fill('delayed');
  await dialog.getByRole('button', { name: '确认重命名', exact: true }).click();
  await dialog.getByRole('button', { name: '查询原操作结果', exact: true }).click({ timeout: 22_000 });
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('tabpanel', { name: 'content/units/delayed.json', exact: true })).toBeVisible();
  expect(await page.evaluate(() => (window as any).contentRequests.filter((action: string) => action === 'rename_content').length)).toBe(1);
  expect(await stat(join(projectPath, 'content/units/twin.json')).catch(() => null)).toBeNull();
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/delayed.json'), 'utf8')).health).toBe(137);
});

test('同名重命名不丢失非法源码输入也不触发保存决策', async ({ desktopHost }) => {
  const { page, projectPath } = desktopHost;
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = await expand(page); await tree.locator('[data-path="content/units/broken.json"]').click();
  const source = page.getByRole('tabpanel', { name: 'content/units/broken.json', exact: true }).locator('.cm-content');
  await source.fill('{unfinished');
  await source.press('Tab');
  await expect(page.getByRole('button', { name: '重命名', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: '重命名', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '重命名内容', exact: true });
  await dialog.getByRole('button', { name: '确认重命名', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('dialog', { name: '继续内容操作', exact: true })).toHaveCount(0);
  await expect(source).toHaveText('{unfinished');
  expect(await readFile(join(projectPath, 'content/units/broken.json'), 'utf8')).toBe('{invalid');
});

test('内容定位由用户点击打开系统资源管理器并选中实际文件', async ({ desktopHost }, info) => {
  const { page, projectPath, temporary } = desktopHost;
  const probe = join(temporary, 'selection-probe.ps1');
  await writeFile(probe, `\ufeffparam([string]$Target='', [string]$Existing='')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$shell=New-Object -ComObject Shell.Application
if (-not $Target) { (($shell.Windows() | ForEach-Object { $_.HWND }) -join ','); exit 0 }
$deadline=[DateTime]::UtcNow.AddSeconds(10)
while ([DateTime]::UtcNow -lt $deadline) {
  foreach ($window in $shell.Windows()) {
    try {
      foreach ($item in $window.Document.SelectedItems()) {
        if ($item.Path -eq $Target) {
          $fresh=([string]$window.HWND) -notin ($Existing -split ',')
          [PSCustomObject]@{selected=$item.Path;newWindow=$fresh} | ConvertTo-Json -Compress
          if ($fresh) { $window.Quit() }
          exit 0
        }
      }
    } catch { }
  }
  Start-Sleep -Milliseconds 100
}
throw '未观察到资源管理器选中目标文件'
`, 'utf8');
  const run = (args: string[]) => execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', probe, ...args],
    { windowsHide: true, encoding: 'utf8', timeout: 15_000 });
  const existing = run([]).trim();
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = await expand(page); await tree.locator('[data-path="content/blocks/twin.json"]').click();
  await page.getByRole('button', { name: '定位文件', exact: true }).click();
  await expect(page.locator('footer').getByRole('status')).toHaveText('已定位文件');
  const result = run(['-Target', join(projectPath, 'content/blocks/twin.json'), '-Existing', existing || 'none']);
  expect(JSON.parse(result).selected.toLowerCase()).toBe(join(projectPath, 'content/blocks/twin.json').toLowerCase());
  await info.attach('原生资源管理器选中实际文件', { body: result, contentType: 'application/json' });
});
