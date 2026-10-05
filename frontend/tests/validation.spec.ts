import { test, expect } from './desktop-fixture';
import { execFileSync } from 'node:child_process';
import { readFile, writeFile, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';

test('真实校验同名字段与坏源码定位、过期报告退路', async ({ desktopHost }, info) => {
  const { page, projectPath } = desktopHost;
  await writeFile(join(projectPath, 'content/blocks/twin.json'), '{"type":"Wall","health":"wrong"}');
  await writeFile(join(projectPath, 'content/units/root-array.json'), '[]');
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  await expect(page.getByRole('tree', { name: '工程文件', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '校验工程', exact: true }).first().click();
  const report = page.getByRole('region', { name: '校验报告', exact: true });
  await expect(report.getByText('校验未完成', { exact: false })).toHaveCount(0);
  const healthIssue = report.locator('li').filter({ hasText: 'content/blocks/twin.json' }).filter({ hasText: 'health' });
  await expect(healthIssue.first()).toBeVisible();
  await healthIssue.first().getByRole('button').click();
  const block = page.getByRole('tabpanel', { name: 'content/blocks/twin.json' });
  await expect(block).toBeVisible();
  const health = block.locator('[data-field="health"] input').first();
  await expect(health).toBeFocused();
  await health.fill('432'); await health.press('Enter');
  await expect(report.getByText('报告已过期。', { exact: false })).toBeVisible();
  await report.locator('li').filter({ hasText: 'content/units/broken.json' }).first().getByRole('button').click();
  await expect(page.getByRole('tabpanel', { name: 'content/units/broken.json' })).toBeVisible();
  await expect(page.getByText('报告位置已过期或存在未应用输入，已打开对应文件，请重新校验。')).toBeVisible();
  await report.getByRole('button', { name: '重新校验', exact: true }).click();
  await report.locator('li').filter({ hasText: 'content/units/broken.json' }).first().getByRole('button').click();
  const source = page.getByRole('tabpanel', { name: 'content/units/broken.json' }).locator('.cm-content');
  await expect(source).toBeFocused();
  const selection = await source.evaluate(element => {
    const current = window.getSelection();
    const range = document.createRange(); range.selectNodeContents(element);
    if (current?.anchorNode) range.setEnd(current.anchorNode, current.anchorOffset);
    return { text: element.textContent, offset: range.toString().length, focus: element.contains(current?.anchorNode ?? null) };
  });
  expect(selection.focus).toBe(true); expect(selection.offset).toBe(1);
  await page.getByRole('button', { name: '导出模组', exact: true }).click();
  await expect(page.getByRole('alert').first()).toContainText('源码');
  await info.attach('源码定位选择', { body: JSON.stringify(selection), contentType: 'application/json' });
  const arrayIssue = report.locator('li').filter({ hasText: 'content/units/root-array.json' }).first();
  await arrayIssue.getByRole('button').click();
  const arrayPanel = page.getByRole('tabpanel', { name: 'content/units/root-array.json' });
  await expect(arrayPanel).toBeVisible();
  await arrayPanel.getByRole('button', { name: '表单', exact: true }).click();
  await arrayIssue.getByRole('button').click();
  await expect(arrayPanel.locator('.cm-content')).toBeVisible();
  await expect(page.getByText('已打开源码：content/units/root-array.json；此问题未提供精确行列。', { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('校验与源码定位.png') });
});

test('真实导出原生取消后保留保存状态、正常ZIP与全部输入起点', async ({ desktopHost }, info) => {
  const { page, projectPath, temporary, pid } = desktopHost;
  await rm(join(projectPath, 'content/units/broken.json'));
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true }); await expect(tree).toBeVisible();
  while (await tree.locator('[aria-expanded="false"]').count()) await tree.locator('[aria-expanded="false"]').first().click();
  await tree.locator('[data-path="content/blocks/twin.json"]').click();
  const panel = page.getByRole('tabpanel', { name: 'content/blocks/twin.json' });
  await expect(panel).toBeVisible();
  while (await panel.locator('button[aria-label^="展开"]:not(:disabled)').count()) await panel.locator('button[aria-label^="展开"]:not(:disabled)').first().click();
  const health = panel.locator('[data-field="health"] input').first();
  await health.fill('765'); await health.press('Enter');
  const output = join(temporary, '中文 导出.zip');
  const dialog = (action: string) => execFileSync('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass',
    '-File', resolve(import.meta.dirname, 'folder-dialog.ps1'), '-TestProcessId', String(pid), '-DialogName', '另存为',
    '-Action', action, '-ProjectPath', output], { windowsHide: true, encoding: 'utf8', timeout: 20_000, stdio: ['ignore', 'pipe', 'pipe'] });
  await page.getByRole('button', { name: '导出模组', exact: true }).click();
  await info.attach('真实保存选择器取消', { body: dialog('cancel'), contentType: 'text/plain' });
  await expect(page.getByText('已保存，已取消导出', { exact: true })).toBeVisible();
  expect(JSON.parse(await readFile(join(projectPath, 'content/blocks/twin.json'), 'utf8')).health).toBe(765);
  await expect(page.getByRole('tab')).not.toContainText('●');
  await page.getByRole('button', { name: '导出模组', exact: true }).click();
  // Keep the real picker open past the transport deadline; recover only the
  // original operation after selecting, never open a second save picker.
  const recover = page.getByRole('button', { name: '查询操作结果', exact: true });
  await expect(recover).toBeVisible({ timeout: 20_000 });
  try { await info.attach('真实保存选择器提交', { body: dialog('select'), contentType: 'text/plain' }); }
  catch (error) { await info.attach('保存选择器失败控件', { body: String((error as { stdout?: string }).stdout ?? ''), contentType: 'text/plain' }); throw error; }
  await expect.poll(() => readFile(output).then(() => true).catch(() => false)).toBe(true);
  await recover.click();
  await expect(page.getByText(`已导出：${output}`, { exact: true })).toBeVisible();
  const payload = execFileSync(resolve(import.meta.dirname, '../../.venv-web/Scripts/python.exe'), ['-X', 'utf8', '-c',
    "import sys,json,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None; print(json.dumps({'entries':z.namelist(),'data':json.loads(z.read('content/blocks/twin.json'))},ensure_ascii=False))", output], { windowsHide: true, encoding: 'utf8' });
  expect(JSON.parse(payload).data.health).toBe(765);
  await info.attach('实际ZIP读回', { body: payload, contentType: 'application/json' });
  const inputs = await page.locator('input,textarea,select,[contenteditable="true"]').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(), css = getComputedStyle(element);
    return { field: element.closest('[data-field]')?.getAttribute('data-field'), label: element.getAttribute('aria-label'), width: rect.width,
      textStart: rect.x + parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft), inset: parseFloat(css.borderLeftWidth) + parseFloat(css.paddingLeft) };
  }));
  expect(inputs.filter(item => item.width > 0).every(item => Number.isFinite(item.textStart))).toBe(true);
  await info.attach('全部输入起点', { body: JSON.stringify(inputs), contentType: 'application/json' });
  await page.screenshot({ path: info.outputPath('真实导出与校验报告.png') });
});
