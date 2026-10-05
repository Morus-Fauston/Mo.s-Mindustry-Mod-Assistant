import { describe, expect, it } from 'vitest';
import { DesktopError } from '../bridge/desktop';
import type { EditingState } from '../workspace/types';
import { createEditingClient, type EditingTransport } from './client';

const initial: EditingState = { sessionId: 'one', revision: 2, documents: [],
  history: { canUndo: false, canRedo: false, undoDescription: '', redoDescription: '' }, autoSaveInterval: 180 };

describe('编辑操作的真实请求身份', () => {
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
