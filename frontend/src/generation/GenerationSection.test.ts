import { describe, expect, it } from 'vitest';
import { DesktopError } from '../bridge/desktop';
import { createEditingClient, type EditingTransport } from '../editing/client';
import type { EditingState } from '../workspace/types';
import type { GenerationCandidate } from './types';
import { createGenerationBridge, type GenerationOwner } from './GenerationSection';

const state: EditingState = { sessionId: 's', revision: 2, documents: [], autoSaveInterval: 0,
  history: { canUndo: false, canRedo: false, undoDescription: '', redoDescription: '' } };
const candidate: GenerationCandidate = { sessionId: 's', candidateId: 'candidate-a', outputs: [] };
const owner: GenerationOwner = { sessionId: 's', path: 'content/units/a.json', revision: 2, resourceRevision: 0, disabled: false, hasDrafts: false };
async function setup(failPreview = false) {
  const actions: string[] = [], cancelled: [string, string][] = [], notices: string[] = [];
  const transport: EditingTransport = {
    async request<T>(action: string) {
      actions.push(action);
      if (action === 'editing_state') return state as T;
      if (action === 'preview_generation') {
        if (failPreview) throw new DesktopError('BRIDGE_TIMEOUT', '等待生成结果超时。');
        return { state, candidate } as T;
      }
      return { state: { ...state, revision: 3 }, outputs: [] } as T;
    },
    async recoverRequest<T>() { actions.push('query'); return { state, candidate } as T; },
  };
  const editing = createEditingClient(transport); editing.reset('s'); await editing.refresh();
  let subscriptions = 0;
  const subscribe = editing.subscribe;
  editing.subscribe = callback => {
    subscriptions++; let active = true;
    const stop = subscribe(callback);
    return () => { if (active) { active = false; subscriptions--; stop(); } };
  };
  let current = { ...owner };
  const bridge = createGenerationBridge(editing, () => current, async (session, id) => { cancelled.push([session, id]); }, notice => notices.push(notice));
  return { editing, bridge, actions, cancelled, notices, subscriptions: () => subscriptions,
    change: (update: Partial<GenerationOwner>) => { current = { ...current, ...update }; } };
}

describe('生成模块真实编辑客户端接线', () => {
  it('正常预览从完整result取candidate，不把editing.run的state误作候选或自动清理', async () => {
    const test = await setup();
    expect(await test.bridge.callbacks(owner).onPreview([{ suffix: '-outline' }])).toEqual(candidate);
    expect(test.cancelled).toEqual([]);
    expect(test.subscriptions()).toBe(0);
    await test.bridge.callbacks(owner).onConfirm(candidate.candidateId, false);
    expect(test.editing.getSnapshot().state?.revision).toBe(3);
    expect(test.actions).toEqual(['editing_state', 'preview_generation', 'confirm_generation']);
  });
  it('超时预览只查询原请求，恢复后主动释放候选而不重新生成', async () => {
    const test = await setup(true);
    await expect(test.bridge.callbacks(owner).onPreview([{ suffix: '-outline' }])).rejects.toThrow('超时');
    expect(test.editing.getSnapshot().uncertain).toBe(true);
    expect(test.subscriptions()).toBe(1);
    await test.editing.recover();
    await Promise.resolve(); await Promise.resolve();
    expect(test.cancelled).toEqual([['s', 'candidate-a']]);
    expect(test.notices).toContain('已取回并释放原预览，请重新预览。');
    expect(test.actions).toEqual(['editing_state', 'preview_generation', 'query']);
    test.bridge.observeResult(); await Promise.resolve();
    expect(test.cancelled).toHaveLength(1);
    expect(test.subscriptions()).toBe(0);
  });
  it('超时后卸载仍清理同会话恢复候选，不通知新内容或使用新session取消', async () => {
    const test = await setup(true);
    await expect(test.bridge.callbacks(owner).onPreview([])).rejects.toThrow();
    test.bridge.setActive(false); test.change({ path: 'content/units/other.json' });
    await test.editing.recover(); await Promise.resolve(); await Promise.resolve();
    expect(test.cancelled).toEqual([['s', 'candidate-a']]); expect(test.notices).toEqual([]);
  });
  it('工程reset使等待恢复的订阅释放，旧结果不会清理新会话候选', async () => {
    const test = await setup(true);
    await expect(test.bridge.callbacks(owner).onPreview([])).rejects.toThrow();
    test.editing.reset('other');
    test.bridge.observeResult();
    expect(test.cancelled).toEqual([]); expect(test.notices).toEqual([]);
    expect(test.subscriptions()).toBe(0);
  });
  it('草稿、共享禁用或资源修订变化时拒绝开始，不调用flush或生成', async () => {
    for (const update of [{ hasDrafts: true }, { disabled: true }, { resourceRevision: 1 }, { revision: 3 }, { sessionId: 'other' }]) {
      const test = await setup(); test.change(update);
      await expect(test.bridge.callbacks(owner).onPreview([])).rejects.toThrow();
      expect(test.actions).toEqual(['editing_state']);
    }
  });
  it('旧回调取消只携带捕获的session和候选，不受草稿或当前版本影响', async () => {
    const test = await setup(); const callbacks = test.bridge.callbacks(owner);
    test.change({ sessionId: 'other', revision: 99, hasDrafts: true, disabled: true });
    test.bridge.setActive(false);
    await callbacks.onCancel('old-candidate');
    expect(test.cancelled).toEqual([['s', 'old-candidate']]);
    expect(test.actions).toEqual(['editing_state']);
  });
  it('恢复后清理失败提供重试，重复重试不并发取消，清理成功才允许新生成', async () => {
    const test = await setup(true); let attempts = 0, finish!: () => void;
    const notices: string[] = [];
    const bridge = createGenerationBridge(test.editing, () => owner, async () => {
      attempts++;
      if (attempts === 1) throw new Error('清理连接中断');
      await new Promise<void>(resolve => { finish = resolve; });
    }, text => notices.push(text));
    await expect(bridge.callbacks(owner).onPreview([])).rejects.toThrow();
    await test.editing.recover();
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    expect(notices.at(-1)).toContain('清理失败');
    await expect(bridge.callbacks(owner).onPreview([])).rejects.toThrow('清理');
    const first = bridge.retryCleanup(), second = bridge.retryCleanup();
    await Promise.resolve();
    expect(attempts).toBe(2);
    finish(); await Promise.all([first, second]);
    expect(notices.at(-1)).toContain('已取回并释放');
  });
  it('结果已过期时释放订阅并提示关闭工程，不重复生成来猜原结果', async () => {
    const actions: string[] = [], notices: string[] = [];
    const editing = createEditingClient({
      async request<T>(action: string) { actions.push(action); if (action === 'editing_state') return state as T; throw new DesktopError('BRIDGE_TIMEOUT', '超时'); },
      async recoverRequest<T>(): Promise<T> { actions.push('query'); throw new DesktopError('RESULT_EXPIRED', '结果已过期'); },
    });
    editing.reset('s'); await editing.refresh();
    const bridge = createGenerationBridge(editing, () => owner, async () => { throw new Error('不得凭空取消'); }, text => notices.push(text));
    await expect(bridge.callbacks(owner).onPreview([])).rejects.toThrow('超时');
    await expect(editing.recover()).rejects.toThrow('过期');
    expect(notices).toEqual(['原预览结果已不可恢复，请关闭工程释放候选后重新打开。']);
    bridge.observeResult(); expect(notices).toHaveLength(1);
    expect(actions).toEqual(['editing_state', 'preview_generation', 'query', 'editing_state']);
  });
});
