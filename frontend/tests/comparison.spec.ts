import { test, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join, resolve } from 'node:path';
import type { Locator, Page, TestInfo } from '@playwright/test';

const comparison = (page: Page) => page.getByRole('region', { name: '只读参考与内容对比', exact: true });
const python = resolve(import.meta.dirname, '../../.venv-web/Scripts/python.exe');

async function openCurrent(page: Page, projectPath: string) {
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true });
  await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/units/twin.json"]').click();
  await expect(comparison(page).getByRole('button', { name: '打开参考目录', exact: true })).toBeEnabled();
  return tree;
}

async function referenceFixture(temporary: string) {
  const folder = join(temporary, '中文 空格参考目录'), archive = join(temporary, '中文 空格参考压缩包.zip');
  await mkdir(join(folder, 'content/units'), { recursive: true });
  await mkdir(join(folder, 'content/blocks'), { recursive: true });
  await writeFile(join(folder, 'mod.json'), JSON.stringify({ name: 'readonly-reference', displayName: '中文 只读参考' }));
  await writeFile(join(folder, 'content/units/twin.json'), JSON.stringify({ type: 'flying', health: 421,
    referenceNull: null, referenceFlag: false, referenceObject: { nested: [1, 2, 3] } }));
  await writeFile(join(folder, 'content/blocks/twin.json'), JSON.stringify({ type: 'Wall', health: 901 }));
  await writeFile(join(folder, 'content/units/invalid.json'), '{invalid-reference');
  execFileSync(python, ['-X', 'utf8', '-c',
    "import sys,zipfile,pathlib; root=pathlib.Path(sys.argv[1]); z=zipfile.ZipFile(sys.argv[2],'w',zipfile.ZIP_DEFLATED); [z.write(p,p.relative_to(root).as_posix()) for p in root.rglob('*') if p.is_file()]; z.close()",
    folder, archive], { windowsHide: true, timeout: 10_000 });
  return { folder, archive };
}

async function filesDigest(root: string, prefix = ''): Promise<Record<string, string>> {
  const result: Record<string, string> = {};
  for (const entry of await readdir(join(root, prefix), { withFileTypes: true })) {
    const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) Object.assign(result, await filesDigest(root, relative));
    else if (entry.isFile()) result[relative] = createHash('sha256').update(await readFile(join(root, relative))).digest('hex');
  }
  return result;
}

async function nativeSelection(page: Page, pid: number, kind: 'folder' | 'zip', action: 'select' | 'cancel', path: string, info: TestInfo) {
  await comparison(page).getByRole('button', { name: kind === 'folder' ? '打开参考目录' : '打开参考压缩包', exact: true }).click();
  const output = execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    resolve(import.meta.dirname, 'folder-dialog.ps1'), '-TestProcessId', String(pid), '-DialogName', kind === 'folder' ? '选择文件夹' : '打开',
    '-Action', action, '-ProjectPath', path], { windowsHide: true, encoding: 'utf8', timeout: 20_000 });
  await info.attach(`原生${kind === 'folder' ? '目录' : 'ZIP'}${action === 'select' ? '选择' : '取消'}`, { body: output, contentType: 'text/plain' });
}

async function confirmTwin(panel: Locator, category = 'units') {
  await panel.getByRole('combobox', { name: '内容类别', exact: true }).selectOption(category);
  // The native size=5 select is a listbox, not a combobox.
  await expect(panel.getByRole('listbox', { name: '参考内容', exact: true })).toBeEnabled();
  await panel.getByRole('listbox', { name: '参考内容', exact: true }).selectOption('twin');
  await panel.getByRole('button', { name: '确认比较', exact: true }).click();
  await expect(panel.getByRole('table', { name: '实际字段对比', exact: true })).toBeVisible();
  await expect(panel.getByRole('button', { name: '取消待选参考', exact: true })).toHaveCount(0);
}

async function expectHealth(panel: Locator, current: number, reference: number) {
  const row = panel.getByRole('table', { name: '实际字段对比', exact: true })
    .getByRole('rowheader', { name: /health/ }).locator('..');
  await expect.poll(async () => Number(await row.locator('td').nth(0).locator('span').first().textContent())).toBe(current);
  await expect.poll(async () => Number(await row.locator('td').nth(1).locator('span').first().textContent())).toBe(reference);
  await expect(row).toHaveAttribute('data-different', 'true');
}

async function measureInputs(page: Page, info: TestInfo, name: string) {
  const rows = await page.locator('input,textarea,select,[contenteditable="true"]').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { tag: element.tagName, id: element.id, width: rect.width, visible: rect.width > 0 && rect.height > 0,
      textStart: rect.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft),
      inset: parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft), right: rect.right, viewport: innerWidth };
  }));
  expect(rows.filter(row => row.visible).length).toBeGreaterThan(0);
  expect(rows.filter(row => row.visible).every(row => Number.isFinite(row.textStart) && row.right <= row.viewport + 1)).toBe(true);
  await info.attach(name, { body: JSON.stringify(rows), contentType: 'application/json' });
}

test('参考目录原生取消与中文空格路径、真实未保存值对比及切页保留来源', async ({ desktopHost }, info) => {
  const { page, pid, projectPath, temporary } = desktopHost;
  const { folder } = await referenceFixture(temporary);
  const originals = await filesDigest(folder), projectBefore = await filesDigest(projectPath);
  const tree = await openCurrent(page, projectPath), panel = comparison(page);
  await nativeSelection(page, pid, 'folder', 'cancel', folder, info);
  await expect(panel).toContainText('已取消选择，原对比保持不变。');
  await nativeSelection(page, pid, 'folder', 'select', folder, info);
  await confirmTwin(panel);
  await expectHealth(panel, 137, 421);
  await expect(panel.getByRole('list', { name: '参考读取提示' })).toContainText('已跳过无法解析的 JSON 内容');
  const selected = await panel.getByRole('combobox', { name: '参考来源', exact: true }).inputValue();
  expect(selected).not.toBe('vanilla');
  expect(selected).not.toBe('');
  const current = page.getByRole('tabpanel', { name: 'content/units/twin.json', exact: true });
  await current.getByRole('textbox', { name: '生命值', exact: true }).fill('239');
  await current.getByRole('textbox', { name: '生命值', exact: true }).press('Tab');
  await expectHealth(panel, 239, 421);
  expect(JSON.parse(await readFile(join(projectPath, 'content/units/twin.json'), 'utf8')).health).toBe(137);
  await tree.locator('[data-path="content/blocks/twin.json"]').click();
  await expectHealth(panel, 823, 421);
  await expect(panel.getByRole('combobox', { name: '参考来源', exact: true })).toHaveValue(selected);
  await expect(panel).toContainText('当前文件：content/blocks/twin.json');
  await tree.locator('[data-path="content/units/twin.json"]').click();
  await expectHealth(panel, 239, 421);
  await expect(page.getByRole('tree', { name: '工程文件', exact: true })).not.toContainText('中文 只读参考');
  await measureInputs(page, info, '参考目录与全部输入文本起点');
  await panel.getByRole('table', { name: '实际字段对比', exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: info.outputPath('目录只读参考与真实未保存对比.png') });
  expect(await filesDigest(folder)).toEqual(originals);
  expect(await filesDigest(projectPath)).toEqual(projectBefore);
  await info.attach('目录与工程文件保持原字节', { body: JSON.stringify({ reference: originals, project: projectBefore }), contentType: 'application/json' });
});

test('参考ZIP原生取消、中文空格路径与取消待选保留已确认对比', async ({ desktopHost }, info) => {
  const { page, pid, projectPath, temporary } = desktopHost;
  const { folder, archive } = await referenceFixture(temporary);
  const archiveBefore = await readFile(archive), sourceBefore = await filesDigest(folder), projectBefore = await filesDigest(projectPath);
  await openCurrent(page, projectPath); const panel = comparison(page);
  await nativeSelection(page, pid, 'zip', 'cancel', archive, info);
  await expect(panel).toContainText('已取消选择，原对比保持不变。');
  await nativeSelection(page, pid, 'zip', 'select', archive, info);
  await confirmTwin(panel);
  await expectHealth(panel, 137, 421);
  const selected = await panel.getByRole('combobox', { name: '参考来源', exact: true }).inputValue();
  await nativeSelection(page, pid, 'folder', 'select', folder, info);
  await expect(panel.getByRole('button', { name: '取消待选参考', exact: true })).toBeEnabled();
  await expectHealth(panel, 137, 421);
  await panel.getByRole('button', { name: '取消待选参考', exact: true }).click();
  await expect(panel).toContainText('已取消待选参考，原对比保持不变。');
  await expect(panel.getByRole('combobox', { name: '参考来源', exact: true })).toHaveValue(selected);
  await expectHealth(panel, 137, 421);
  await expect(page.getByRole('button', { name: '撤销', exact: true })).toBeDisabled();
  await measureInputs(page, info, 'ZIP参考全部输入文本起点');
  expect(await readFile(archive)).toEqual(archiveBefore);
  expect(await filesDigest(folder)).toEqual(sourceBefore);
  expect(await filesDigest(projectPath)).toEqual(projectBefore);
  await page.screenshot({ path: info.outputPath('ZIP参考取消待选保持原结果.png') });
});

test('损坏参考中文反馈保留原结果，当前坏源码不能假装有效比较', async ({ desktopHost }, info) => {
  const { page, pid, projectPath, temporary } = desktopHost;
  const { archive } = await referenceFixture(temporary);
  const invalidZip = join(temporary, '损坏 中文压缩包.zip'), invalidFolder = join(temporary, '无效 中文参考');
  await writeFile(invalidZip, 'not a zip');
  await mkdir(join(invalidFolder, 'content/units'), { recursive: true });
  await writeFile(join(invalidFolder, 'content/units/broken.json'), '{broken');
  const tree = await openCurrent(page, projectPath), panel = comparison(page);
  await nativeSelection(page, pid, 'zip', 'select', archive, info); await confirmTwin(panel);
  const selected = await panel.getByRole('combobox', { name: '参考来源', exact: true }).inputValue();
  await nativeSelection(page, pid, 'zip', 'select', invalidZip, info);
  await expect(panel.getByRole('alert')).toContainText('无法读取 ZIP 参考');
  await expectHealth(panel, 137, 421);
  await nativeSelection(page, pid, 'folder', 'select', invalidFolder, info);
  await expect(panel.getByRole('alert')).toContainText('参考中没有可读取的 JSON 内容');
  await expect(panel.getByRole('combobox', { name: '参考来源', exact: true })).toHaveValue(selected);
  await expectHealth(panel, 137, 421);
  await tree.locator('[data-path="content/units/broken.json"]').click();
  await expect(panel).toBeVisible();
  await expect(panel.getByRole('button', { name: '确认比较', exact: true })).toBeDisabled();
  await expect(panel.getByRole('button', { name: '打开参考目录', exact: true })).toBeDisabled();
  await expect(panel.getByRole('combobox', { name: '参考来源', exact: true })).toHaveValue(selected);
  await tree.locator('[data-path="content/units/twin.json"]').click();
  await expectHealth(panel, 137, 421);
  await expect(panel.getByRole('button', { name: '确认比较', exact: true })).toBeEnabled();
  expect(await readFile(invalidZip, 'utf8')).toBe('not a zip');
  expect(await readFile(join(invalidFolder, 'content/units/broken.json'), 'utf8')).toBe('{broken');
  await page.screenshot({ path: info.outputPath('无效来源反馈后恢复当前对比.png') });
});

test('打开参考真实响应延迟后只查询原请求并释放恢复来源', async ({ desktopHost }, info) => {
  test.setTimeout(90_000);
  const { page, pid, projectPath, temporary } = desktopHost;
  const { folder } = await referenceFixture(temporary), originals = await filesDigest(folder);
  await openCurrent(page, projectPath);
  await page.evaluate(() => {
    const host = window as any, original = host.pywebview.api.request;
    host.referenceRequests = [];
    host.pywebview.api.request = async (envelope: any) => {
      host.referenceRequests.push({ action: envelope.action, requestId: envelope.requestId });
      const response = await original(envelope);
      // Only delay transport delivery after the real Python/native operation.
      if (envelope.action === 'open_reference' && response.ok) await new Promise(resolve => setTimeout(resolve, 17_000));
      return response;
    };
  });
  await nativeSelection(page, pid, 'folder', 'select', folder, info);
  await page.getByRole('button', { name: '查询操作结果', exact: true }).click({ timeout: 22_000 });
  await expect(page.getByText('已取回并释放原参考来源，请重新选择。', { exact: true })).toBeVisible();
  await expect(comparison(page).getByRole('button', { name: '打开参考目录', exact: true })).toBeEnabled();
  await expect(comparison(page).getByRole('button', { name: '取消待选参考', exact: true })).toHaveCount(0);
  const requests = await page.evaluate(() => (window as any).referenceRequests as { action: string; requestId: string }[]);
  expect(requests.filter(item => item.action === 'open_reference')).toHaveLength(1);
  expect(requests.filter(item => item.action === 'release_reference')).toHaveLength(1);
  expect(await filesDigest(folder)).toEqual(originals);
  await info.attach('超时只执行一次打开且回收真实来源', { body: JSON.stringify(requests), contentType: 'application/json' });
});
