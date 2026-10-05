import { describe, expect, it } from 'vitest';
import { DesktopError } from '../bridge/desktop';
import { createEditingClient, type EditingTransport } from '../editing/client';
import type { EditingState } from '../workspace/types';
import type { SourceDescriptor } from './types';
import { createComparisonController } from './controller';
import { createComparisonBridge, type ComparisonOwner } from './ComparisonSection';

const state: EditingState = { sessionId: 's', revision: 2, documents: [], autoSaveInterval: 0,
  history: { canUndo: false, canRedo: false, undoDescription: '', redoDescription: '' } };
const source: SourceDescriptor = { sourceId: 'external-a', kind: 'folder', label: '参考工程', categories: [], warnings: [] };
const owner: ComparisonOwner = { sessionId: 's', path: 'content/units/a.json', revision: 2, disabled: false, hasDrafts: false };
async function setup(options: { timeout?: boolean; source?: SourceDescriptor | null; recoveryError?: string; releaseFails?: boolean } = {}) {
  const actions: string[] = [], operations: { action: string; payload: Record<string, unknown> }[] = [];
  const calls: { action: string; payload: Record<string, unknown>; session: string }[] = [], notices: string[] = [];
  const opened = options.source === undefined ? source : options.source;
  const transport: EditingTransport = {
    async request<T>(action: string, payload: Record<string, unknown>) {
      actions.push(action);
      operations.push({ action, payload });
      if (action === 'editing_state') return state as T;
      if (options.timeout) throw new DesktopError('BRIDGE_TIMEOUT', '等待选择结果超时');
      return { state, source: opened } as T;
    },
    async recoverRequest<T>() {
      actions.push('query');
      if (options.recoveryError) throw new DesktopError(options.recoveryError, '结果未知或过期');
      return { state, source: opened } as T;
    },
  };
  const editing = createEditingClient(transport); editing.reset('s'); await editing.refresh();
  let subscriptions = 0, releases = 0;
  const subscribe = editing.subscribe;
  editing.subscribe = callback => {
    subscriptions++; let active = true; const stop = subscribe(callback);
    return () => { if (active) { active = false; subscriptions--; stop(); } };
  };
  let current = { ...owner };
  const bridge = createComparisonBridge(editing, () => current, async <T>(action: string, payload: Record<string, unknown>, session: string) => {
    calls.push({ action, payload, session });
    if (action === 'release_reference') {
      releases++; if (options.releaseFails && releases === 1) throw new Error('清理中断');
      return { released: true } as T;
    }
    if (action === 'reference_sources') return { sources: [source] } as T;
    if (action === 'reference_candidates_for_compare') return { sourceId: source.sourceId, category: 'units', candidates: [], offset: 0, total: 0, hasMore: false } as T;
    return { sessionId: 's', currentPath: owner.path, revision: 2, sourceId: source.sourceId, category: 'units', name: 'dagger', rows: [] } as T;
  }, text => notices.push(text));
  return { editing, bridge, transport, actions, operations, calls, notices, subscriptions: () => subscriptions,
    change: (update: Partial<ComparisonOwner>) => { current = { ...current, ...update }; } };
}
const settle = async () => { for (let index = 0; index < 8; index++) await Promise.resolve(); };

describe('只读对照实际编辑客户端接线', () => {
  it('正常打开返回完整来源，不误释放、不传本地路径，也不把state当source', async () => {
    const test = await setup();
    expect(await test.bridge.callbacks(owner).onOpen('folder')).toEqual(source);
    expect(test.actions).toEqual(['editing_state', 'open_reference']);
    expect(test.operations[1]).toEqual({ action: 'open_reference', payload: { kind: 'folder', expectedRevision: 2 } });
    expect(test.calls).toEqual([]); expect(test.subscriptions()).toBe(0);
  });
  it('正常取消原生对话框返回null', async () => {
    const test = await setup({ source: null });
    expect(await test.bridge.callbacks(owner).onOpen('zip')).toBeNull();
    expect(test.calls).toEqual([]); expect(test.subscriptions()).toBe(0);
  });
  it('列表查询与比较是真实只读请求，比较携带路径与权威revision', async () => {
    const test = await setup(), callbacks = test.bridge.callbacks(owner);
    await callbacks.onSources(); await callbacks.onCandidates(source.sourceId, 'units', 'dagger');
    await callbacks.onCompare(source.sourceId, 'units', 'dagger');
    expect(test.calls).toEqual([
      { action: 'reference_sources', payload: {}, session: 's' },
      { action: 'reference_candidates_for_compare', payload: { sourceId: source.sourceId, category: 'units', query: 'dagger', offset: 0 }, session: 's' },
      { action: 'compare_reference', payload: { sourceId: source.sourceId, category: 'units', name: 'dagger', path: owner.path, expectedRevision: 2 }, session: 's' },
    ]);
    expect(test.actions).toEqual(['editing_state']);
  });
  it('草稿阻止比较但不禁止读取来源，也不把内存未保存当成前端草稿', async () => {
    const test = await setup(); test.change({ hasDrafts: true });
    await expect(test.bridge.callbacks(owner).onCompare(source.sourceId, 'units', 'dagger')).rejects.toThrow('字段');
    await test.bridge.callbacks(owner).onSources();
    expect(test.calls).toHaveLength(1);
  });
  it('超时只查询原请求，恢复source释放一次并提示重选', async () => {
    const test = await setup({ timeout: true });
    await expect(test.bridge.callbacks(owner).onOpen('folder')).rejects.toThrow('超时');
    expect(test.subscriptions()).toBe(1);
    await test.editing.recover(); await settle(); test.bridge.observeResult(); await settle();
    expect(test.actions).toEqual(['editing_state', 'open_reference', 'query']);
    expect(test.calls).toEqual([{ action: 'release_reference', payload: { sourceId: source.sourceId }, session: 's' }]);
    expect(test.notices.at(-1)).toContain('请重新选择'); expect(test.subscriptions()).toBe(0);
  });
  it('超时后卸载仍使用原session清理，reset则结束订阅', async () => {
    const test = await setup({ timeout: true });
    await expect(test.bridge.callbacks(owner).onOpen('folder')).rejects.toThrow();
    const count = test.notices.length;
    test.bridge.setActive(false); test.change({ path: 'content/units/b.json' });
    await test.editing.recover(); await settle();
    expect(test.calls[0].session).toBe('s'); expect(test.notices).toHaveLength(count);
    const reset = await setup({ timeout: true });
    await expect(reset.bridge.callbacks(owner).onOpen('zip')).rejects.toThrow();
    reset.editing.reset('next'); expect(reset.subscriptions()).toBe(0); expect(reset.calls).toEqual([]);
  });
  it('释放失败可重试，清理期间禁止新打开', async () => {
    const test = await setup({ timeout: true, releaseFails: true });
    await expect(test.bridge.callbacks(owner).onOpen('folder')).rejects.toThrow();
    await test.editing.recover(); await settle();
    expect(test.notices.at(-1)).toContain('清理失败');
    await expect(test.bridge.callbacks(owner).onOpen('zip')).rejects.toThrow('清理');
    await Promise.all([test.bridge.retryCleanup(), test.bridge.retryCleanup()]);
    expect(test.calls.filter(call => call.action === 'release_reference')).toHaveLength(2);
    expect(test.notices.at(-1)).toContain('请重新选择');
  });
  it('结果过期不重开对话框，提示关闭工程并解除恢复订阅', async () => {
    const test = await setup({ timeout: true, recoveryError: 'RESULT_EXPIRED' });
    await expect(test.bridge.callbacks(owner).onOpen('folder')).rejects.toThrow();
    await expect(test.editing.recover()).rejects.toThrow('过期');
    expect(test.notices.at(-1)).toContain('关闭工程'); expect(test.subscriptions()).toBe(0);
    expect(test.actions.filter(action => action === 'open_reference')).toHaveLength(1);
    await expect(test.bridge.callbacks(owner).onOpen('zip')).rejects.toThrow('关闭工程');
  });
  it('结果未知保留查询能力，说明重启前记录未保存内容，不指引被门禁禁止的关闭工程', async () => {
    const test = await setup({ timeout: true, recoveryError: 'REQUEST_UNKNOWN' });
    await expect(test.bridge.callbacks(owner).onOpen('folder')).rejects.toThrow();
    await expect(test.editing.recover()).rejects.toThrow();
    expect(test.notices.at(-1)).toContain('继续查询原操作结果');
    expect(test.notices.at(-1)).toContain('重新启动程序');
    expect(test.notices.at(-1)).toContain('未保存内容');
    expect(test.notices.at(-1)).toContain('记录');
    expect(test.notices.at(-1)).not.toContain('关闭工程');
    expect(test.editing.getSnapshot().uncertain).toBe(true);
    expect(test.actions.filter(action => action === 'open_reference')).toHaveLength(1);
    test.editing.reset('next'); expect(test.subscriptions()).toBe(0);
  });
  it('旧回调只释放捕获session，切路径或revision的比较被拒绝', async () => {
    const test = await setup(), callbacks = test.bridge.callbacks(owner);
    test.change({ sessionId: 'next', path: 'content/units/b.json', revision: 3 }); test.bridge.setActive(false);
    await callbacks.onRelease(source.sourceId);
    expect(test.calls[0]).toEqual({ action: 'release_reference', payload: { sourceId: source.sourceId }, session: 's' });
    await expect(callbacks.onCompare(source.sourceId, 'units', 'dagger')).rejects.toThrow();
  });
  it('正常打开的迟到结果交由已卸载controller释放，不走超时恢复分支', async () => {
    const test = await setup(); let finish!: (value: unknown) => void;
    test.transport.request = async <T>() => await new Promise<unknown>(resolve => { finish = resolve; }) as T;
    const controller = createComparisonController();
    controller.start('s', owner.path, owner.revision, test.bridge.callbacks(owner));
    const opening = controller.open('folder');
    controller.stop(); test.bridge.setActive(false);
    finish({ state, source }); await opening;
    expect(test.calls).toEqual([{ action: 'release_reference', payload: { sourceId: source.sourceId }, session: 's' }]);
    expect(test.notices).toEqual([]); expect(test.subscriptions()).toBe(0);
  });
  it('同会话切文档保留当前来源，后续比较使用新文档', async () => {
    const test = await setup(), callbacks = test.bridge.callbacks(owner);
    const controller = createComparisonController(); controller.start('s', owner.path, 2, callbacks);
    await controller.open('folder');
    const next = { ...owner, path: 'content/units/b.json' };
    test.change(next); controller.updateContext(next.path, 2, test.bridge.callbacks(next));
    expect(controller.getSnapshot().sources).toEqual([source]);
    expect(test.calls).toEqual([]);
    await test.bridge.callbacks(next).onCompare(source.sourceId, 'units', 'dagger');
    expect(test.calls[0].payload.path).toBe(next.path);
    controller.stop(); await settle();
  });
});
