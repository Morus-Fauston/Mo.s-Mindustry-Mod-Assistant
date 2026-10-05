import { DesktopError } from '../bridge/desktop';
import type { EditingState } from '../workspace/types';

export interface EditingTransport {
  request<T>(action: string, payload: Record<string, unknown>, sessionId: string | null, requestId?: string): Promise<T>;
  recoverRequest<T>(action: string, payload: Record<string, unknown>, sessionId: string | null, requestId: string): Promise<T>;
}

export interface EditingSnapshot { state: EditingState | null; busy: boolean; uncertain: boolean;
  result?: { action: string; requestId: string; data: unknown } }
interface Operation { action: string; payload: Record<string, unknown>; sessionId: string | null; requestId: string }

export function uncertainResult(error: unknown): boolean {
  return error instanceof DesktopError && ['BRIDGE_TIMEOUT', 'BRIDGE_FAILURE', 'INVALID_RESPONSE',
    'REQUEST_PENDING', 'REQUEST_UNKNOWN'].includes(error.code);
}

/** A single mutation lane. Only Python owns documents and undo history. */
export function createEditingClient(transport: EditingTransport) {
  let snapshot: EditingSnapshot = { state: null, busy: false, uncertain: false };
  let sessionId: string | null = null;
  let generation = 0;
  let unresolved: Operation | null = null;
  const subscribers = new Set<() => void>();
  function publish(update: Partial<EditingSnapshot>) {
    snapshot = { ...snapshot, ...update };
    subscribers.forEach(callback => callback());
  }
  function accept(state: EditingState, current: number) {
    if (current !== generation || state.sessionId !== sessionId) return;
    if (!snapshot.state || state.revision >= snapshot.state.revision) publish({ state });
  }
  async function refresh() {
    const current = generation;
    const state = await transport.request<EditingState>('editing_state', {}, sessionId);
    accept(state, current);
    return state;
  }
  async function execute(operation: Operation, recovering: boolean) {
    const current = generation;
    publish({ busy: true });
    try {
      const call = recovering ? transport.recoverRequest : transport.request;
      const data = await call<EditingState | { state: EditingState }>(operation.action, operation.payload, operation.sessionId, operation.requestId);
      if (current !== generation) throw new DesktopError('STALE_SESSION', '工程已切换。');
      const state = 'state' in data ? data.state : data;
      if (state.sessionId !== sessionId || !Number.isInteger(state.revision) || !Array.isArray(state.documents)) {
        throw new DesktopError('INVALID_RESPONSE', '操作返回资料无效，请查询原操作结果。');
      }
      accept(state, current);
      unresolved = null;
      publish({ uncertain: false, result: { action: operation.action, requestId: operation.requestId, data } });
      return state;
    } catch (error) {
      if (current === generation) {
        if (uncertainResult(error)) {
          unresolved = operation;
          publish({ uncertain: true });
        } else {
          unresolved = null;
          // A partial save may have succeeded for some documents. Read actual state.
          try { await refresh(); publish({ uncertain: false }); }
          catch { publish({ uncertain: true }); }
        }
      }
      throw error;
    } finally { if (current === generation) publish({ busy: false }); }
  }
  return {
    getSnapshot: () => snapshot,
    subscribe(callback: () => void) { subscribers.add(callback); return () => { subscribers.delete(callback); }; },
    reset(nextSessionId: string | null) {
      generation += 1;
      sessionId = nextSessionId;
      unresolved = null;
      publish({ state: null, busy: false, uncertain: false, result: undefined });
    },
    refresh,
    async run(action: string, payload: Record<string, unknown> = {}) {
      if (snapshot.uncertain) throw new DesktopError('RESULT_UNCONFIRMED', '请先查询原操作结果。');
      if (snapshot.busy) throw new DesktopError('BUSY', '请等待当前操作完成。');
      if (!snapshot.state) throw new DesktopError('NOT_READY', '编辑资料尚未就绪。');
      return execute({ action, payload: { ...payload, expectedRevision: snapshot.state.revision },
        sessionId, requestId: crypto.randomUUID() }, false);
    },
    async recover() {
      if (snapshot.busy) throw new DesktopError('BUSY', '请等待当前操作完成。');
      if (unresolved) return execute(unresolved, true);
      const state = await refresh();
      publish({ uncertain: false });
      return state;
    },
  };
}
