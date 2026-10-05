import { DesktopError } from '../bridge/desktop';
import { uncertainResult, type EditingSnapshot, type EditingTransport } from '../editing/client';
import type { EditingState } from '../workspace/types';
import type { PreferencesPatch, PreferencesState, WorkbenchLayout } from './types';

export interface PreferencesSnapshot {
  state: PreferencesState | null;
  layout: WorkbenchLayout | null;
  busy: boolean;
  uncertain: boolean;
  error: string;
}
interface EditingOwner { getSnapshot(): EditingSnapshot; refresh(): Promise<EditingState> }
interface Options { debounceMs?: number; getSessionId?: () => string | null }
interface Job {
  action: 'preferences_state' | 'update_settings' | 'update_layout';
  payload: Record<string, unknown>;
  sequence?: number;
  resolve?: () => void;
  reject?: (error: unknown) => void;
}
interface Operation { action: string; payload: Record<string, unknown>; sessionId: string | null; requestId: string; job: Job }
interface LayoutUpdate { layout: WorkbenchLayout; sequence: number }
const message = (error: unknown) => error instanceof Error ? error.message : '配置操作未完成，请重试。';
const record = (value: unknown): value is Record<string, unknown> => Boolean(value) && typeof value === 'object' && !Array.isArray(value);
function parseState(value: unknown): PreferencesState {
  const settings = (item: unknown) => record(item) && ['light', 'dark'].includes(item.theme as string)
    && ['zh_en', 'en_zh', 'zh', 'en'].includes(item.display_name_mode as string)
    && Number.isSafeInteger(item.auto_save_interval) && Number(item.auto_save_interval) >= 0 && Number(item.auto_save_interval) <= 3600
    && Number.isSafeInteger(item.sprite_zoom) && Number(item.sprite_zoom) >= 1 && Number(item.sprite_zoom) <= 8;
  const layout = record(value) && record(value.layout) ? value.layout : null;
  if (!record(value) || !Number.isSafeInteger(value.revision) || Number(value.revision) < 0
      || !settings(value.values) || !settings(value.defaults) || !Array.isArray(value.warnings)
      || value.warnings.some(item => typeof item !== 'string') || !layout
      || typeof layout.filesVisible !== 'boolean' || typeof layout.previewVisible !== 'boolean'
      || ['leftWidth', 'rightWidth', 'previewRatio'].some(key => layout[key] !== null
        && (typeof layout[key] !== 'number' || !Number.isFinite(layout[key]) || Number(layout[key]) <= 0))) {
    throw new DesktopError('INVALID_RESPONSE', '配置返回资料无效，请查询原操作结果。');
  }
  return structuredClone(value) as unknown as PreferencesState;
}

/** Global preferences own one transport queue; Python still owns document state and history. */
export function createPreferencesController(transport: EditingTransport, editing: EditingOwner, options: Options = {}) {
  const session = options.getSessionId ?? (() => editing.getSnapshot().state?.sessionId ?? null);
  const listeners = new Set<() => void>(), queue: Job[] = [];
  const waiters: { resolve: () => void; reject: (error: unknown) => void; failureVersion: number }[] = [];
  let state: PreferencesState | null = null, optimistic: LayoutUpdate | null = null;
  let pendingLayout: LayoutUpdate | null = null, sequence = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let active = true, running = false, uncertain = false, error = '';
  let writeFailure: unknown = null;
  let failureVersion = 0, latestFailure: unknown = null;
  let unresolved: Operation | null = null;
  let snapshot: PreferencesSnapshot = { state: null, layout: null, busy: false, uncertain: false, error: '' };
  function publish() {
    snapshot = { state, layout: optimistic?.layout ?? state?.layout ?? null,
      busy: running || !uncertain && Boolean(queue.length || pendingLayout), uncertain, error };
    if (active) listeners.forEach(listener => listener());
    if (!running && (uncertain || !queue.length && !pendingLayout)) {
      for (const waiter of waiters.splice(0)) {
        if (uncertain) waiter.reject(new Error(error || '请先查询原配置操作结果。'));
        else if (waiter.failureVersion < failureVersion) waiter.reject(latestFailure);
        else if (writeFailure) waiter.reject(writeFailure);
        else waiter.resolve();
      }
    }
  }
  function accept(next: PreferencesState, job?: Job) {
    if (!state || next.revision >= state.revision) state = next;
    if (job?.sequence !== undefined && optimistic && optimistic.sequence <= job.sequence) optimistic = null;
    publish();
  }
  async function refreshEditing() {
    if (!active) return;
    try { await editing.refresh(); }
    catch (cause) { error = `配置已确认，编辑资料刷新失败：${message(cause)}`; publish(); }
  }
  async function readLatest() {
    // Reads are safe to retry after a session transition; mutations never are.
    for (let attempt = 0; attempt < 3; attempt++) {
      const owner = session();
      try {
        const next = parseState(await transport.request('preferences_state', {}, owner, crypto.randomUUID()));
        if (owner !== session()) continue;
        accept(next); return;
      } catch (cause) {
        if (owner !== session()) continue;
        throw cause;
      }
    }
    throw new DesktopError('STALE_SESSION', '工程连续切换，请在当前工程重新读取配置。');
  }
  function clearTimer() { if (timer !== undefined) clearTimeout(timer); timer = undefined; }
  function scheduleLayout() {
    clearTimer();
    if (active && pendingLayout && !uncertain) timer = setTimeout(() => { timer = undefined; enqueueLayout(); }, options.debounceMs ?? 250);
  }
  function enqueueLayout() {
    clearTimer();
    if (!pendingLayout) return;
    const queued = queue.find(job => job.action === 'update_layout');
    if (queued) { queued.payload = { layout: pendingLayout.layout }; queued.sequence = pendingLayout.sequence; }
    else queue.push({ action: 'update_layout', payload: { layout: pendingLayout.layout }, sequence: pendingLayout.sequence });
    pendingLayout = null; publish(); pump();
  }
  function rollbackLayout(job: Job) {
    if (job.sequence !== undefined && optimistic && optimistic.sequence <= job.sequence) optimistic = null;
  }
  async function execute(job: Job) {
    if (job.action === 'preferences_state') {
      await readLatest(); await refreshEditing(); return;
    }
    if (!state) throw new DesktopError('NOT_READY', '请先读取配置。');
    const operation: Operation = { action: job.action, payload: { ...job.payload, expectedPreferencesRevision: state.revision },
      sessionId: session(), requestId: crypto.randomUUID(), job };
    let next: PreferencesState;
    try {
      const result = await transport.request<{ preferences: unknown }>(operation.action, operation.payload, operation.sessionId, operation.requestId);
      next = parseState(result?.preferences);
    } catch (cause) {
      if (uncertainResult(cause) || cause instanceof DesktopError && cause.code === 'STALE_SESSION') {
        unresolved = operation; uncertain = true; clearTimer();
      } else {
        rollbackLayout(job);
        try { await readLatest(); await refreshEditing(); } catch { uncertain = true; clearTimer(); }
      }
      throw cause;
    }
    accept(next, job);
    if (operation.sessionId !== session()) {
      try { await readLatest(); }
      catch (cause) { uncertain = true; clearTimer(); throw cause; }
    }
    await refreshEditing();
  }
  function pump() {
    if (!active || running || uncertain || !queue.length) return;
    const job = queue.shift()!;
    running = true; error = ''; publish();
    void execute(job).then(() => {
      writeFailure = null;
      running = false; publish(); job.resolve?.(); pump();
    }, cause => {
      if (job.action !== 'preferences_state') { writeFailure = latestFailure = cause; failureVersion++; }
      running = false; error = message(cause); publish(); job.reject?.(cause); pump();
    });
  }
  function ready() {
    if (!active) throw new DesktopError('INACTIVE', '配置界面已关闭。');
    if (uncertain) throw new DesktopError('RESULT_UNCONFIRMED', '请先查询原配置操作结果。');
  }
  function submit(action: Job['action'], payload: Record<string, unknown>): Promise<void> {
    try { ready(); } catch (cause) { return Promise.reject(cause); }
    return new Promise<void>((resolve, reject) => { queue.push({ action, payload, resolve, reject }); publish(); pump(); });
  }
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    load: () => submit('preferences_state', {}),
    updateSettings: (patch: PreferencesPatch) => submit('update_settings', { patch: structuredClone(patch) }),
    updateLayout(layout: WorkbenchLayout) {
      ready();
      if (!state) throw new DesktopError('NOT_READY', '请先读取配置。');
      optimistic = { layout: structuredClone(layout), sequence: ++sequence };
      pendingLayout = optimistic; publish(); scheduleLayout();
    },
    async flush() {
      ready(); enqueueLayout();
      if (!running && !queue.length) { if (writeFailure) throw writeFailure; return; }
      await new Promise<void>((resolve, reject) => { waiters.push({ resolve, reject, failureVersion }); pump(); });
    },
    async recover() {
      if (!active) throw new DesktopError('INACTIVE', '配置界面已关闭。');
      if (running) throw new DesktopError('BUSY', '请等待当前配置操作完成。');
      running = true; error = ''; publish();
      let terminal: unknown;
      try {
        if (unresolved) {
          const operation = unresolved;
          try {
            const result = await transport.recoverRequest<{ preferences: unknown }>(operation.action, operation.payload,
              operation.sessionId, operation.requestId);
            accept(parseState(result?.preferences), operation.job); unresolved = null;
          } catch (cause) {
            if (uncertainResult(cause)) throw cause;
            rollbackLayout(operation.job); unresolved = null; terminal = cause;
          }
        }
        await readLatest(); uncertain = false;
        writeFailure = terminal ?? null;
        await refreshEditing();
        if (terminal) throw terminal;
      } catch (cause) {
        if (unresolved || !terminal) uncertain = true;
        error = message(cause); throw cause;
      } finally {
        running = false; publish();
        if (!uncertain) { scheduleLayout(); pump(); }
      }
    },
    setActive(value: boolean) {
      if (active === value) return;
      active = value;
      if (!active) clearTimer();
      else { scheduleLayout(); pump(); }
      publish();
    },
  };
}
