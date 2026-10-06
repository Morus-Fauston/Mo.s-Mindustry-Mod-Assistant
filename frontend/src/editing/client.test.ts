import { describe, expect, it } from 'vitest';
import { DesktopError } from '../bridge/desktop';
import type { EditingState } from '../workspace/types';
import { createEditingClient, type EditingTransport } from './client';

const initial: EditingState = { sessionId: 'one', revision: 2, documents: [],
  history: { canUndo: false, canRedo: false, undoDescription: '', redoDescription: '' }, autoSaveInterval: 180 };

describe('关闭工程沿用唯一编辑串行通道', () => {
  const closed = { project: null, state: { ...initial, sessionId: 'closed', revision: 3 } };
  it.each([false, true])('采用空工程新身份；超时仅查询原ID并禁止重复关闭，timeout=%s', async timeout => {
    const calls: { action: string; payload: unknown; session: string | null; id?: string }[] = [];
    let queried: unknown;
    const client = createEditingClient({
      async request<T>(action: string, payload: unknown, session: string | null, id?: string) {
        calls.push({ action, payload, session, id });
        if (action === 'editing_state') return { ...initial, sessionId: session } as T;
        if (timeout) throw new DesktopError('BRIDGE_TIMEOUT', '超时');
        return closed as T;
      },
      async recoverRequest<T>(action: string, payload: unknown, session: string | null, id: string) {
        queried = { action, payload, session, id }; return closed as T;
      },
    });
    client.reset('one'); await client.refresh();
    if (timeout) {
      await expect(client.run('close_project', { decision: 'discard' })).rejects.toThrow('超时');
      await expect(client.run('close_project', { decision: 'discard' })).rejects.toThrow();
      await client.recover(); expect(queried).toEqual(calls[1]);
    } else await client.run('close_project', { decision: 'discard' });
    expect(calls[1]).toMatchObject({ payload: { decision: 'discard', expectedRevision: 2 }, session: 'one' });
    expect(client.getSnapshot()).toMatchObject({ state: closed.state, uncertain: false, busy: false,
      result: { action: 'close_project', data: closed } });
    await client.refresh(); expect(calls.at(-1)?.session).toBe('closed');
    expect(calls.filter(call => call.action === 'close_project')).toHaveLength(1);
  });
  it('失败不清空原state；关闭后迟到旧读取不复活工程', async () => {
    let fail = true, reads = 0, finish!: (state: EditingState) => void;
    const client = createEditingClient({
      async request<T>(action: string) {
        if (action === 'editing_state') {
          if (++reads <= 2) return initial as T;
          return await new Promise<EditingState>(resolve => { finish = resolve; }) as T;
        }
        if (fail) throw new DesktopError('SAVE_FAILED', '保存失败');
        return closed as T;
      }, async recoverRequest<T>() { return closed as T; },
    });
    client.reset('one'); await client.refresh();
    await expect(client.run('close_project', { decision: 'save' })).rejects.toThrow('保存失败');
    expect(client.getSnapshot().state).toEqual(initial);
    fail = false;
    const read = client.refresh(), rejected = expect(read).rejects.toMatchObject({ code: 'STALE_SESSION' });
    await client.run('close_project', { decision: 'discard' }); finish(initial); await rejected;
    expect(client.getSnapshot().state).toEqual(closed.state);
  });
});

describe('工程创建与历史的受控会话转换', () => {
  const state = (sessionId: string, revision: number, canRedo = false): EditingState => ({ ...initial, sessionId, revision,
    history: { canUndo: !canRedo, canRedo, undoDescription: canRedo ? '' : '新建工程', redoDescription: canRedo ? '新建工程' : '' } });
  const project = (sessionId: string) => ({ sessionId, name: '新工程', root: 'D:/new-mod', tree: [] });
  it('创建→撤销到空工作台→重做保留真实历史/result，并始终使用新session发后续请求', async () => {
    const calls: { action: string; session: string | null }[] = [];
    const client = createEditingClient({
      async request<T>(action: string, _payload: unknown, session: string | null) {
        calls.push({ action, session });
        if (action === 'editing_state') return initial as T;
        if (action === 'create_project') return { state: state('created', 3), project: project('created') } as T;
        if (action === 'undo') return { ...state('empty', 4, true), project: null } as T;
        return { ...state('redone', 5), project: project('redone') } as T;
      },
      async recoverRequest<T>() { return initial as T; },
    });
    client.reset('one'); await client.refresh();
    await client.run('create_project');
    expect(client.getSnapshot().state?.sessionId).toBe('created');
    await client.run('undo');
    expect(client.getSnapshot().state?.history.canRedo).toBe(true);
    expect(client.getSnapshot().result?.data).toMatchObject({ project: null, sessionId: 'empty' });
    expect(client.getSnapshot().busy).toBe(false);
    await client.run('redo');
    expect(client.getSnapshot().state?.sessionId).toBe('redone');
    expect(calls).toEqual([{ action: 'editing_state', session: 'one' }, { action: 'create_project', session: 'one' },
      { action: 'undo', session: 'created' }, { action: 'redo', session: 'empty' }]);
  });
  it.each([
    ['set_field', { state: state('new', 3), project: project('new') }],
    ['create_project', { state: state('new', 3), project: project('wrong') }],
    ['undo', { ...state('new', 3) }],
    ['redo', { ...state('new', 3), project: undefined }],
    ['set_field', { revision: 3, documents: [] }],
  ])('%s非法转换保留原state并进入结果未确认', async (action, data) => {
    const client = createEditingClient({
      async request<T>(action: string) { return (action === 'editing_state' ? initial : data) as T; },
      async recoverRequest<T>() { return data as T; },
    });
    client.reset('one'); await client.refresh();
    await expect(client.run(action as string)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    expect(client.getSnapshot().state).toEqual(initial); expect(client.getSnapshot().uncertain).toBe(true);
    expect(client.getSnapshot().busy).toBe(false);
  });
  it('创建超时用原请求身份恢复，不重建历史、不重复创建', async () => {
    const calls: { action: string; session: string | null; id?: string }[] = [];
    let recovered: unknown;
    const client = createEditingClient({
      async request<T>(action: string, _payload: unknown, session: string | null, id?: string) {
        calls.push({ action, session, id });
        if (action === 'editing_state') return initial as T;
        throw new DesktopError('BRIDGE_TIMEOUT', '超时');
      },
      async recoverRequest<T>(action: string, _payload: unknown, session: string | null, id: string) {
        recovered = { action, session, id }; return { state: state('new', 3), project: project('new') } as T;
      },
    });
    client.reset('one'); await client.refresh(); await expect(client.run('create_project')).rejects.toThrow('超时');
    await client.recover();
    expect(recovered).toEqual(calls[1]); expect(calls).toHaveLength(2);
    expect(client.getSnapshot()).toMatchObject({ state: { sessionId: 'new' }, uncertain: false, busy: false,
      result: { action: 'create_project', requestId: calls[1].id } });
  });
  it('合法转换拒绝此前在途refresh返回的旧state', async () => {
    let reads = 0, finish!: (value: EditingState) => void;
    const client = createEditingClient({
      async request<T>(action: string) {
        if (action === 'editing_state') { if (++reads === 1) return initial as T; return await new Promise<EditingState>(resolve => { finish = resolve; }) as T; }
        return { state: state('new', 3), project: project('new') } as T;
      }, async recoverRequest<T>() { return initial as T; },
    });
    client.reset('one'); await client.refresh();
    const read = client.refresh(), rejected = expect(read).rejects.toMatchObject({ code: 'STALE_SESSION' });
    await client.run('create_project'); finish(initial); await rejected;
    expect(client.getSnapshot().state?.sessionId).toBe('new');
  });
  it.each([false, true])('reset后迟到的工程转换不可覆盖新state，recover=%s', async recovering => {
    let finish!: (value: unknown) => void;
    const client = createEditingClient({
      async request<T>(action: string, _payload: unknown, session: string | null) {
        if (action === 'editing_state') return { ...initial, sessionId: session } as T;
        if (recovering) throw new DesktopError('BRIDGE_TIMEOUT', '超时');
        return await new Promise<unknown>(resolve => { finish = resolve; }) as T;
      },
      async recoverRequest<T>() { return await new Promise<unknown>(resolve => { finish = resolve; }) as T; },
    });
    client.reset('one'); await client.refresh();
    if (recovering) await expect(client.run('create_project')).rejects.toThrow('超时');
    const pending = recovering ? client.recover() : client.run('create_project');
    const rejected = expect(pending).rejects.toMatchObject({ code: 'STALE_SESSION' });
    client.reset('other'); await client.refresh();
    finish({ state: state('late', 3), project: project('late') }); await rejected;
    expect(client.getSnapshot()).toMatchObject({ state: { sessionId: 'other' }, busy: false, uncertain: false });
    expect(client.getSnapshot().result).toBeUndefined();
  });
  it('已知操作失败后的刷新若跨reset迟到，不改变新会话的busy与uncertain', async () => {
    let reads = 0, finish!: (value: unknown) => void;
    const client = createEditingClient({
      async request<T>(action: string, _payload: unknown, session: string | null) {
        if (action !== 'editing_state') throw new DesktopError('SAVE_FAILED', '保存失败');
        if (++reads === 2) return await new Promise<unknown>(resolve => { finish = resolve; }) as T;
        return { ...initial, sessionId: session } as T;
      }, async recoverRequest<T>() { return initial as T; },
    });
    client.reset('one'); await client.refresh();
    const failed = expect(client.run('save_opened')).rejects.toThrow('保存失败');
    for (let index = 0; index < 4; index++) await Promise.resolve();
    client.reset('other'); await client.refresh(); finish(initial); await failed;
    expect(client.getSnapshot()).toMatchObject({ state: { sessionId: 'other' }, busy: false, uncertain: false });
  });
});

describe('编辑操作的真实请求身份', () => {
  it('导出超时查询接收真实保存状态和报告，不重复打开原生选择器', async () => {
    let requests = 0;
    const result = { state: { ...initial, revision: 3 }, cancelled: true, exported: false,
      report: { sessionId: 'one', revision: 3, issues: [] } };
    const client = createEditingClient({
      async request<T>(action: string) {
        if (action === 'editing_state') return initial as T;
        requests++; throw new DesktopError('BRIDGE_TIMEOUT', '超时');
      },
      async recoverRequest<T>() { return result as T; },
    });
    client.reset('one'); await client.refresh();
    await expect(client.run('export_project')).rejects.toThrow('超时');
    await client.recover();
    expect(requests).toBe(1);
    expect(client.getSnapshot().state).toEqual(result.state);
    expect(client.getSnapshot().result?.data).toEqual(result);
    expect(client.getSnapshot().result?.action).toBe('export_project');
    client.reset('two');
    expect(client.getSnapshot().result).toBeUndefined();
  });
  it('已执行结果过期后只刷新权威状态，刷新失败仍可恢复且不重放', async () => {
    const calls: string[] = [];
    let failedRefresh = false;
    const transport: EditingTransport = {
      async request<T>(action: string) {
        calls.push(action);
        if (action === 'editing_state') {
          if (failedRefresh) throw new DesktopError('BRIDGE_FAILURE', '刷新失败');
          return { ...initial, revision: calls.length > 2 ? 3 : 2 } as T;
        }
        throw new DesktopError('BRIDGE_TIMEOUT', '超时');
      },
      async recoverRequest<T>(): Promise<T> { calls.push('query'); throw new DesktopError('RESULT_EXPIRED', '操作已经执行，请刷新状态'); },
    };
    const client = createEditingClient(transport);
    client.reset('one'); await client.refresh();
    await expect(client.run('set_source', { text: '{}' })).rejects.toThrow('超时');
    failedRefresh = true;
    await expect(client.recover()).rejects.toThrow('操作已经执行');
    expect(client.getSnapshot().uncertain).toBe(true);
    failedRefresh = false;
    await client.recover();
    expect(client.getSnapshot().state?.revision).toBe(3);
    expect(client.getSnapshot().uncertain).toBe(false);
    expect(calls).toEqual(['editing_state', 'set_source', 'query', 'editing_state', 'editing_state']);
  });
  it('超时后只查询原请求，确认之前不允许继续修改', async () => {
    const calls: { action: string; payload: Record<string, unknown>; id?: string }[] = [];
    let recoveredId = '';
    const transport: EditingTransport = {
      async request<T>(action: string, payload: Record<string, unknown>, _session: string | null, id?: string) {
        calls.push({ action, payload, id });
        if (action === 'editing_state') return initial as T;
        throw new DesktopError('BRIDGE_TIMEOUT', '超时');
      },
      async recoverRequest<T>(_action: string, _payload: Record<string, unknown>, _session: string | null, id: string) {
        recoveredId = id;
        return { ...initial, revision: 3 } as T;
      },
    };
    const client = createEditingClient(transport);
    client.reset('one');
    await client.refresh();
    await expect(client.run('set_field', { path: 'content/units/a.json', field: 'health', value: 200 })).rejects.toThrow('超时');
    await expect(client.run('undo')).rejects.toThrow('查询');
    expect(calls).toHaveLength(2);
    expect(calls[1].payload.expectedRevision).toBe(2);
    await client.recover();
    expect(recoveredId).toBe(calls[1].id);
    expect(client.getSnapshot().state?.revision).toBe(3);
    expect(client.getSnapshot().uncertain).toBe(false);
  });

  it('同一次操作等待期间拒绝双击，旧会话结果不覆盖新工程', async () => {
    let release!: (state: EditingState) => void;
    const transport: EditingTransport = {
      async request<T>(action: string, _payload: Record<string, unknown>, session: string | null) {
        if (action === 'editing_state') return { ...initial, sessionId: session } as T;
        return await new Promise<EditingState>(resolve => { release = resolve; }) as T;
      },
      async recoverRequest<T>() { return initial as T; },
    };
    const client = createEditingClient(transport);
    client.reset('one'); await client.refresh();
    const pending = client.run('save_opened');
    const rejected = expect(pending).rejects.toThrow('工程已切换');
    await expect(client.run('save_opened')).rejects.toThrow('等待');
    client.reset('two'); await client.refresh();
    release({ ...initial, revision: 9 });
    await rejected;
    expect(client.getSnapshot().state?.sessionId).toBe('two');
    expect(client.getSnapshot().state?.revision).toBe(2);
  });

  it('已知保存失败后同步权威快照，不将失败伪装为成功', async () => {
    let failed = false;
    const transport: EditingTransport = {
      async request<T>(action: string) {
        if (action === 'editing_state') return { ...initial, revision: failed ? 5 : 2 } as T;
        failed = true; throw new DesktopError('SAVE_FAILED', '无法保存');
      },
      async recoverRequest<T>() { return initial as T; },
    };
    const client = createEditingClient(transport);
    client.reset('one'); await client.refresh();
    await expect(client.run('save_opened')).rejects.toThrow('无法保存');
    expect(client.getSnapshot().state?.revision).toBe(5);
    expect(client.getSnapshot().uncertain).toBe(false);
    expect(client.getSnapshot().busy).toBe(false);
  });
});
