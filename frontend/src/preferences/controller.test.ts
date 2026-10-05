import { afterEach, describe, expect, it, vi } from 'vitest';
import { DesktopError } from '../bridge/desktop';
import type { EditingTransport } from '../editing/client';
import type { EditingState } from '../workspace/types';
import type { PreferencesState } from './types';
import { createPreferencesController } from './controller';

const initial = (): PreferencesState => ({ revision: 0,
  defaults: { theme: 'light', display_name_mode: 'zh_en', auto_save_interval: 0, sprite_zoom: 4 },
  values: { theme: 'light', display_name_mode: 'zh_en', auto_save_interval: 0, sprite_zoom: 4, legacy: '保留' },
  layout: { leftWidth: null, rightWidth: null, previewRatio: null, filesVisible: true, previewVisible: true }, warnings: [] });
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
const tick = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); };
function setup() {
  let preferences = initial(), session: string | null = 's1';
  const history = { canUndo: true, canRedo: false, undoDescription: '编辑内容', redoDescription: '' };
  const editingState = (): EditingState => ({ sessionId: session, revision: 17, documents: [], autoSaveInterval: 0, history });
  const refresh = vi.fn(async () => editingState());
  const calls: { action: string; payload: Record<string, unknown>; sessionId: string | null; requestId?: string; recover: boolean }[] = [];
  const results = new Map<string, unknown>();
  let before: ((action: string) => Promise<void>) | null = null;
  let after: ((action: string) => Promise<void>) | null = null;
  let recoveryError: Error | null = null;
  const transport: EditingTransport = {
    async request<T>(action: string, payload: Record<string, unknown>, sessionId: string | null, requestId?: string) {
      calls.push({ action, payload, sessionId, requestId, recover: false });
      await before?.(action);
      if (action === 'preferences_state') return structuredClone(preferences) as T;
      if (payload.expectedPreferencesRevision !== preferences.revision) throw new DesktopError('STALE_PREFERENCES', '配置已变化');
      preferences = { ...preferences, revision: preferences.revision + 1,
        ...(action === 'update_settings' ? { values: { ...preferences.values, ...payload.patch as object } }
          : { layout: payload.layout as PreferencesState['layout'] }) };
      const result = { preferences: structuredClone(preferences), state: { ...editingState(), sessionId: 'poison', revision: 999 } };
      results.set(requestId!, result); await after?.(action); return result as T;
    },
    async recoverRequest<T>(action: string, payload: Record<string, unknown>, sessionId: string | null, requestId: string) {
      calls.push({ action, payload, sessionId, requestId, recover: true });
      if (recoveryError) throw recoveryError;
      return results.get(requestId) as T;
    },
  };
  const editing = { getSnapshot: () => ({ state: editingState(), busy: false, uncertain: false }), refresh };
  const controller = createPreferencesController(transport, editing);
  return { controller, transport, calls, refresh, history, editing, setSession: (next: string | null) => { session = next; },
    setPreferences: (next: PreferencesState) => { preferences = next; }, preferences: () => preferences,
    before: (next: typeof before) => { before = next; }, after: (next: typeof after) => { after = next; },
    recoveryError: (next: Error | null) => { recoveryError = next; } };
}
afterEach(() => { vi.useRealTimers(); });

describe('全局配置串行控制器', () => {
  it('独立配置revision与当前session写入，忽略业务回包并刷新权威编辑资料', async () => {
    const test = setup(); await test.controller.load();
    test.refresh.mockClear(); await test.controller.updateSettings({ theme: 'dark' });
    const write = test.calls.find(call => call.action === 'update_settings')!;
    expect(write.payload).toEqual({ patch: { theme: 'dark' }, expectedPreferencesRevision: 0 });
    expect(write.sessionId).toBe('s1'); expect(write.requestId).toBeTruthy();
    expect(test.controller.getSnapshot().state?.values.theme).toBe('dark');
    expect(test.controller.getSnapshot().state?.values.legacy).toBe('保留');
    expect(test.refresh).toHaveBeenCalledOnce(); expect(test.editing.getSnapshot().state.revision).toBe(17);
    expect(test.editing.getSnapshot().state.history).toBe(test.history);
  });
  it('250ms内布局即时展示但只写最后一份，flush不重复写', async () => {
    vi.useFakeTimers(); const test = setup(); await test.controller.load(); test.calls.length = 0;
    test.controller.updateLayout({ ...initial().layout, leftWidth: 201 });
    test.controller.updateLayout({ ...initial().layout, leftWidth: 239 });
    expect(test.controller.getSnapshot().layout?.leftWidth).toBe(239);
    expect(test.controller.getSnapshot().busy).toBe(true);
    await vi.advanceTimersByTimeAsync(249); expect(test.calls).toEqual([]);
    await vi.advanceTimersByTimeAsync(1); await test.controller.flush();
    expect(test.calls.filter(call => call.action === 'update_layout')).toHaveLength(1);
    expect(test.preferences().layout.leftWidth).toBe(239); expect(test.controller.getSnapshot().busy).toBe(false);
    await test.controller.flush(); expect(test.calls.filter(call => call.action === 'update_layout')).toHaveLength(1);
  });
  it('进行中的布局、即时设置和较新布局共用单队列，revision在发送时取值', async () => {
    vi.useFakeTimers(); const test = setup(); await test.controller.load();
    const pending = deferred<void>(); let first = true;
    test.after(async action => { if (action === 'update_layout' && first) { first = false; await pending.promise; } });
    test.controller.updateLayout({ ...initial().layout, leftWidth: 210 });
    await vi.advanceTimersByTimeAsync(250);
    const setting = test.controller.updateSettings({ sprite_zoom: 5 });
    test.controller.updateLayout({ ...initial().layout, leftWidth: 280 });
    await vi.advanceTimersByTimeAsync(250);
    expect(test.calls.filter(call => call.action.startsWith('update_'))).toHaveLength(1);
    pending.resolve(); await setting; await test.controller.flush();
    const writes = test.calls.filter(call => call.action.startsWith('update_'));
    expect(writes.map(call => call.action)).toEqual(['update_layout', 'update_settings', 'update_layout']);
    expect(writes.map(call => call.payload.expectedPreferencesRevision)).toEqual([0, 1, 2]);
    expect(test.preferences().layout.leftWidth).toBe(280); expect(test.preferences().values.sprite_zoom).toBe(5);
  });
  it('load不覆盖尚未持久化的布局视图', async () => {
    vi.useFakeTimers(); const test = setup(); await test.controller.load();
    test.controller.updateLayout({ ...initial().layout, leftWidth: 250 });
    await test.controller.load(); expect(test.controller.getSnapshot().layout?.leftWidth).toBe(250);
    await test.controller.flush(); expect(test.preferences().layout.leftWidth).toBe(250);
  });
  it('写入超时只查询原requestId，跨工程后确认全局最新配置但不重放', async () => {
    const test = setup(); await test.controller.load();
    test.after(async () => { throw new DesktopError('BRIDGE_TIMEOUT', '超时'); });
    await expect(test.controller.updateSettings({ theme: 'dark' })).rejects.toThrow('超时');
    expect(test.controller.getSnapshot().uncertain).toBe(true);
    const original = test.calls.find(call => call.action === 'update_settings')!;
    test.setSession('s2'); test.after(null); await test.controller.recover();
    const recovery = test.calls.find(call => call.recover)!;
    expect(recovery).toEqual({ ...original, recover: true });
    expect(test.calls.filter(call => call.action === 'update_settings' && !call.recover)).toHaveLength(1);
    expect(test.calls.at(-1)?.action).toBe('preferences_state'); expect(test.calls.at(-1)?.sessionId).toBe('s2');
    expect(test.controller.getSnapshot().state?.values.theme).toBe('dark');
    expect(test.controller.getSnapshot().uncertain).toBe(false);
  });
  it('写请求切session失败仍可查原结果，UNKNOWN期间不允许新写', async () => {
    const test = setup(); await test.controller.load();
    test.after(async () => { test.setSession('s2'); throw new DesktopError('STALE_SESSION', '会话已切换'); });
    await expect(test.controller.updateSettings({ theme: 'dark' })).rejects.toThrow();
    expect(test.controller.getSnapshot().uncertain).toBe(true);
    test.recoveryError(new DesktopError('REQUEST_UNKNOWN', '结果未知'));
    await expect(test.controller.recover()).rejects.toThrow('未知');
    await expect(test.controller.updateSettings({ theme: 'light' })).rejects.toThrow();
    expect(test.calls.filter(call => call.action === 'update_settings' && !call.recover)).toHaveLength(1);
    test.recoveryError(null); test.after(null); await test.controller.recover();
    expect(test.controller.getSnapshot().state?.values.theme).toBe('dark');
  });
  it('确定配置冲突重读权威值并拒绝当前提交，较新的layout视图不冒充已保存', async () => {
    const test = setup(); await test.controller.load();
    test.setPreferences({ ...initial(), revision: 5, values: { ...initial().values, theme: 'dark' } });
    await expect(test.controller.updateSettings({ sprite_zoom: 6 })).rejects.toThrow('变化');
    expect(test.controller.getSnapshot().state?.revision).toBe(5);
    expect(test.controller.getSnapshot().state?.values.sprite_zoom).toBe(4);
    expect(test.controller.getSnapshot().uncertain).toBe(false);
    await test.controller.updateSettings({ sprite_zoom: 6 });
    expect(test.preferences().revision).toBe(6);
  });
  it('卸载清timer并暂停待写，重挂载只写一次；晚到完成不通知已卸载视图', async () => {
    vi.useFakeTimers(); const test = setup(); await test.controller.load();
    const listener = vi.fn(); test.controller.subscribe(listener);
    test.controller.updateLayout({ ...initial().layout, rightWidth: 390 });
    test.controller.setActive(false); listener.mockClear();
    await vi.advanceTimersByTimeAsync(1000);
    expect(test.calls.filter(call => call.action === 'update_layout')).toHaveLength(0);
    expect(listener).not.toHaveBeenCalled();
    const pending = deferred<void>(); test.after(async () => pending.promise);
    test.controller.setActive(true); await vi.advanceTimersByTimeAsync(250);
    test.controller.setActive(false); listener.mockClear(); pending.resolve(); await tick();
    expect(listener).not.toHaveBeenCalled();
    test.controller.setActive(true); await test.controller.flush();
    expect(test.calls.filter(call => call.action === 'update_layout')).toHaveLength(1);
  });
  it('写入已确认但编辑刷新失败不把写入标未知或再次发送', async () => {
    const test = setup(); await test.controller.load();
    test.refresh.mockRejectedValueOnce(new Error('刷新失败'));
    await test.controller.updateSettings({ theme: 'dark' });
    expect(test.controller.getSnapshot().state?.values.theme).toBe('dark');
    expect(test.controller.getSnapshot().uncertain).toBe(false);
    expect(test.controller.getSnapshot().error).toContain('刷新');
    await test.controller.load();
    expect(test.calls.filter(call => call.action === 'update_settings')).toHaveLength(1);
  });
  it('关闭前flush必须报告布局写入失败，并回退到权威布局', async () => {
    vi.useFakeTimers(); const test = setup(); await test.controller.load();
    test.before(async action => { if (action === 'update_layout') throw new DesktopError('PREFERENCES_FAILED', '配置文件被占用'); });
    test.controller.updateLayout({ ...initial().layout, leftWidth: 250 });
    await expect(test.controller.flush()).rejects.toThrow('占用');
    expect(test.controller.getSnapshot().layout?.leftWidth).toBeNull();
    expect(test.controller.getSnapshot().uncertain).toBe(false);
    expect(test.controller.getSnapshot().error).toContain('占用');
    await expect(test.controller.flush()).rejects.toThrow('占用');
  });
  it('原结果已过期或明确旧session时读回全局状态，保留失败反馈而不重放', async () => {
    for (const code of ['RESULT_EXPIRED', 'STALE_SESSION']) {
      const test = setup(); await test.controller.load();
      test.after(async () => { throw new DesktopError('BRIDGE_TIMEOUT', '超时'); });
      await expect(test.controller.updateSettings({ theme: 'dark' })).rejects.toThrow();
      test.setSession('s2'); test.recoveryError(new DesktopError(code, '原结果不可恢复'));
      await expect(test.controller.recover()).rejects.toThrow('不可恢复');
      expect(test.controller.getSnapshot().state?.values.theme).toBe('dark');
      expect(test.controller.getSnapshot().uncertain).toBe(false);
      expect(test.calls.filter(call => call.action === 'update_settings' && !call.recover)).toHaveLength(1);
      expect(test.calls.at(-1)?.action).toBe('preferences_state');
    }
  });
  it('恢复拿到已完成写入后读回失败，再次恢复只重读配置', async () => {
    const test = setup(); await test.controller.load();
    test.after(async () => { throw new DesktopError('BRIDGE_TIMEOUT', '超时'); });
    await expect(test.controller.updateSettings({ theme: 'dark' })).rejects.toThrow();
    test.before(async action => { if (action === 'preferences_state') throw new DesktopError('READ_FAILED', '无法读取配置'); });
    await expect(test.controller.recover()).rejects.toThrow('无法读取');
    expect(test.controller.getSnapshot().uncertain).toBe(true);
    test.before(null); await test.controller.recover();
    expect(test.calls.filter(call => call.recover)).toHaveLength(1);
    expect(test.calls.filter(call => call.action === 'update_settings' && !call.recover)).toHaveLength(1);
    expect(test.controller.getSnapshot().uncertain).toBe(false);
  });
  it('提交中切工程成功回包必须读取新session最新配置，忽略旧业务state', async () => {
    const test = setup(); await test.controller.load();
    test.after(async () => {
      test.setSession('s2');
      test.setPreferences({ ...test.preferences(), revision: 8, values: { ...test.preferences().values, sprite_zoom: 7 } });
    });
    await test.controller.updateSettings({ theme: 'dark' });
    expect(test.controller.getSnapshot().state?.revision).toBe(8);
    expect(test.controller.getSnapshot().state?.values.sprite_zoom).toBe(7);
    expect(test.calls.at(-1)?.action).toBe('preferences_state'); expect(test.calls.at(-1)?.sessionId).toBe('s2');
    expect(test.editing.getSnapshot().state.sessionId).toBe('s2'); expect(test.editing.getSnapshot().state.revision).toBe(17);
  });
  it('flush期间较早布局失败不能被后续设置成功掩盖', async () => {
    vi.useFakeTimers(); const test = setup(); await test.controller.load();
    const pending = deferred<void>();
    test.before(async action => { if (action === 'update_layout') { await pending.promise; throw new Error('布局未保存'); } });
    test.controller.updateLayout({ ...initial().layout, leftWidth: 250 });
    await vi.advanceTimersByTimeAsync(250);
    const settings = test.controller.updateSettings({ theme: 'dark' });
    const flushed = expect(test.controller.flush()).rejects.toThrow('布局未保存');
    pending.resolve(); await settings; await flushed;
    expect(test.preferences().values.theme).toBe('dark'); expect(test.preferences().layout.leftWidth).toBeNull();
  });
  it('无效成功回包保留原请求查询身份，不把未验证配置用于界面', async () => {
    const test = setup(); await test.controller.load();
    const request = test.transport.request;
    test.transport.request = async <T>(...args: Parameters<EditingTransport['request']>) => {
      const result = await request<T>(...args);
      return args[0] === 'update_settings' ? { preferences: { revision: 1 } } as T : result;
    };
    await expect(test.controller.updateSettings({ theme: 'dark' })).rejects.toThrow('无效');
    expect(test.controller.getSnapshot().state?.values.theme).toBe('light');
    expect(test.controller.getSnapshot().uncertain).toBe(true);
    await test.controller.recover(); expect(test.controller.getSnapshot().state?.values.theme).toBe('dark');
    expect(test.calls.filter(call => call.action === 'update_settings' && !call.recover)).toHaveLength(1);
  });
});
