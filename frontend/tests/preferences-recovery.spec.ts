import { test, expect } from './desktop-fixture';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { Page, TestInfo } from '@playwright/test';

interface RecordedRequest {
  action: string;
  requestId: string;
  sessionId: string | null;
  ok?: boolean;
  resultSessionId?: string | null;
  delivered?: boolean;
}
interface RecoveryProbe { requests: RecordedRequest[]; queries: string[] }

async function delaySuccessfulResponse(page: Page, action: string) {
  await page.evaluate(action => {
    const host = window as any;
    const request = host.pywebview.api.request, query = host.pywebview.api.request_result;
    host.preferencesRecoveryProbe = { requests: [], queries: [] };
    host.pywebview.api.request = async (envelope: any) => {
      const call: RecordedRequest = { action: envelope.action, requestId: envelope.requestId, sessionId: envelope.sessionId };
      host.preferencesRecoveryProbe.requests.push(call);
      const response = await request(envelope);
      call.ok = response.ok;
      call.resultSessionId = response.sessionId;
      // The real Python request finishes first. Only delivery of its original
      // response is delayed; request_result keeps its real cached response.
      if (envelope.action === action && response.ok) await new Promise(resolve => setTimeout(resolve, 17_000));
      call.delivered = true;
      return response;
    };
    host.pywebview.api.request_result = async (requestId: string) => {
      host.preferencesRecoveryProbe.queries.push(requestId);
      return query(requestId);
    };
  }, action);
}

async function probe(page: Page): Promise<RecoveryProbe> {
  return page.evaluate(() => (window as any).preferencesRecoveryProbe);
}

async function recordEvidence(page: Page, info: TestInfo, name: string) {
  await info.attach(name, { body: JSON.stringify(await probe(page), null, 2), contentType: 'application/json' });
}

test('真实打开工程响应超时期间阻止配置写入并只查询原打开结果', async ({ desktopHost }, info) => {
  test.setTimeout(60_000);
  const { page, projectPath, temporary } = desktopHost;
  await expect(page.getByRole('button', { name: '设置', exact: true })).toBeEnabled();
  await delaySuccessfulResponse(page, 'open_project');
  await page.getByRole('button').filter({ hasText: projectPath }).click();
  const recover = page.getByRole('button', { name: '查询打开结果', exact: true });
  await expect(recover).toBeVisible({ timeout: 22_000 });
  await expect(recover).toBeEnabled();
  await expect(page.getByRole('alert').filter({ hasText: '桌面程序响应超时' })).toBeVisible();
  for (const name of ['设置', '文件面板', '预览面板', '恢复布局']) {
    await expect(page.getByRole('button', { name, exact: true })).toBeDisabled();
  }
  const statePath = join(temporary, 'config/editor_state.json');
  const settingsPath = join(temporary, 'config/settings.json');
  const beforeState = await readFile(statePath), beforeSettings = await readFile(settingsPath);
  const beforeProbe = await probe(page);
  await page.keyboard.press('Control+b');
  // The real layout debounce is 250 ms; observe past it to catch an illicit write.
  await page.waitForTimeout(400);
  expect(await readFile(statePath)).toEqual(beforeState);
  expect(await readFile(settingsPath)).toEqual(beforeSettings);
  expect((await probe(page)).requests.filter(call => call.action === 'update_layout' || call.action === 'update_settings'))
    .toEqual(beforeProbe.requests.filter(call => call.action === 'update_layout' || call.action === 'update_settings'));
  await page.screenshot({ path: info.outputPath('打开结果未确认时配置入口禁用.png') });
  await recover.click();
  const tree = page.getByRole('tree', { name: '工程文件', exact: true });
  await expect(tree).toBeVisible();
  await expect(page.getByRole('button', { name: '设置', exact: true })).toBeEnabled();
  await expect(page.getByRole('alert').filter({ hasText: '桌面程序响应超时' })).toHaveCount(0);
  for (let level = 0; level < 12 && await tree.locator('[aria-expanded="false"]').count(); level++) {
    await tree.locator('[aria-expanded="false"]').first().click();
  }
  await tree.locator('[data-path="content/units/twin.json"]').click();
  const form = page.getByRole('tabpanel', { name: 'content/units/twin.json', exact: true });
  await expect(form.locator('[data-field="health"] input[type="text"]')).toHaveValue('137');
  await expect.poll(async () => (await probe(page)).requests.find(call => call.action === 'open_project')?.delivered,
    { timeout: 6_000 }).toBe(true);
  const trace = await probe(page), opens = trace.requests.filter(call => call.action === 'open_project');
  expect(opens).toHaveLength(1);
  expect(opens[0].ok).toBe(true);
  expect(opens[0].resultSessionId).toBeTruthy();
  expect(opens[0].resultSessionId).not.toBe(opens[0].sessionId);
  expect(trace.queries).toEqual([opens[0].requestId]);
  expect(trace.requests.find(call => call.action === 'read_document')?.sessionId).toBe(opens[0].resultSessionId);
  await expect(form.locator('[data-field="health"] input[type="text"]')).toHaveValue('137');
  await recordEvidence(page, info, '真实打开仅执行一次且恢复新会话');
});

test('设置模态内查询真实超时写入结果并清除错误且不重复写入', async ({ desktopHost }, info) => {
  test.setTimeout(60_000);
  const { page, temporary } = desktopHost;
  await expect(page.getByRole('button', { name: '设置', exact: true })).toBeEnabled();
  await delaySuccessfulResponse(page, 'update_settings');
  await page.getByRole('button', { name: '设置', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '设置', exact: true });
  await dialog.getByRole('combobox', { name: '主题', exact: true }).selectOption('dark');
  await dialog.getByRole('textbox', { name: '预览倍率', exact: true }).fill('6');
  await dialog.getByRole('button', { name: '应用', exact: true }).click();
  const recover = dialog.getByRole('button', { name: '查询配置结果', exact: true });
  await expect(recover).toBeVisible({ timeout: 22_000 });
  await expect(recover).toBeEnabled();
  await expect(dialog.getByRole('alert')).toContainText('桌面程序响应超时');
  const settingsPath = join(temporary, 'config/settings.json');
  expect(JSON.parse(await readFile(settingsPath, 'utf8'))).toMatchObject({ theme: 'dark', sprite_zoom: 6 });
  await page.screenshot({ path: info.outputPath('设置模态内原请求查询入口.png') });
  await recover.click();
  await expect(recover).toHaveCount(0);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(dialog.getByRole('combobox', { name: '主题', exact: true })).toHaveValue('dark');
  await expect(dialog.getByRole('textbox', { name: '预览倍率', exact: true })).toHaveValue('6');
  await expect(dialog.getByRole('alert')).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: '应用', exact: true })).toBeDisabled();
  await expect(dialog.getByRole('button', { name: '关闭', exact: true })).toBeEnabled();
  await expect.poll(async () => (await probe(page)).requests.find(call => call.action === 'update_settings')?.delivered,
    { timeout: 6_000 }).toBe(true);
  await expect(dialog.getByRole('alert')).toHaveCount(0);
  await dialog.getByRole('button', { name: '关闭', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('alert').filter({ hasText: '桌面程序响应超时' })).toHaveCount(0);
  await page.getByRole('button', { name: '设置', exact: true }).click();
  const reopened = page.getByRole('dialog', { name: '设置', exact: true });
  await expect(reopened.getByRole('combobox', { name: '主题', exact: true })).toHaveValue('dark');
  await expect(reopened.getByRole('textbox', { name: '预览倍率', exact: true })).toHaveValue('6');
  await expect(reopened.getByRole('alert')).toHaveCount(0);
  await reopened.getByRole('button', { name: '关闭', exact: true }).click();
  const trace = await probe(page), updates = trace.requests.filter(call => call.action === 'update_settings');
  expect(updates).toHaveLength(1);
  expect(updates[0].ok).toBe(true);
  expect(trace.queries).toEqual([updates[0].requestId]);
  expect(JSON.parse(await readFile(settingsPath, 'utf8'))).toMatchObject({ theme: 'dark', sprite_zoom: 6 });
  await recordEvidence(page, info, '设置只执行一次且模态恢复后清除超时');
});
