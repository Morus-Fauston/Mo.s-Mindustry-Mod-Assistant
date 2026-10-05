import type { CandidatePage, Comparison, ComparisonCallbacks, ReferenceSelection, SourceDescriptor } from './types';

interface Snapshot {
  sessionId: string;
  sources: SourceDescriptor[];
  pending: SourceDescriptor | null;
  selection: ReferenceSelection | null;
  comparison: Comparison | null;
  page: CandidatePage | null;
  busy: 'sources' | 'open' | 'candidates' | 'compare' | 'cancel' | 'cleanup' | null;
  stale: boolean;
  error: string;
  notice: string;
  cleanupNeeded: boolean;
}
interface Owned { source: SourceDescriptor; actions: ComparisonCallbacks; releasing?: Promise<void> }

const initial = (): Snapshot => ({ sessionId: '', sources: [], pending: null, selection: null, comparison: null,
  page: null, busy: null, stale: false, error: '', notice: '', cleanupNeeded: false });
const message = (failure: unknown) => failure instanceof Error ? failure.message : '参考操作未完成，请重试。';

/** Owns readonly source lifetimes only; current document and history stay in Python. */
export function createComparisonController() {
  let snapshot = initial(), active = false, serial = 0, path = '', revision = 0, refreshRequested = false;
  let compareReady = true;
  let actions: ComparisonCallbacks;
  const owned = new Map<string, Owned>(), listeners = new Set<() => void>();
  const current = (token: number) => active && token === serial;
  function publish(update: Partial<Snapshot>) {
    snapshot = { ...snapshot, ...update };
    snapshot.cleanupNeeded = [...owned.keys()].some(id => id !== snapshot.selection?.sourceId && id !== snapshot.pending?.sourceId);
    listeners.forEach(listener => listener());
  }
  async function release(value: Owned) {
    value.releasing ??= Promise.resolve().then(() => value.actions.onRelease(value.source.sourceId));
    try {
      await value.releasing;
      if (owned.get(value.source.sourceId) === value) {
        owned.delete(value.source.sourceId);
        if (active) publish({ sources: snapshot.sources.filter(source => source.sourceId !== value.source.sourceId) });
      }
    }
    catch (failure) { value.releasing = undefined; throw failure; }
  }
  function releaseDetached(value: Owned) {
    return release(value).catch(failure => {
      console.warn('只读参考清理失败，工程关闭时将统一释放。', message(failure));
    });
  }
  function stop() {
    active = false; serial++; refreshRequested = false;
    const outgoing = [...owned.values()]; owned.clear();
    outgoing.forEach(value => { void releaseDetached(value); });
  }
  async function run(busy: NonNullable<Snapshot['busy']>, work: (token: number, captured: ComparisonCallbacks) => Promise<void>) {
    if (!active || snapshot.busy) return;
    const token = ++serial, captured = actions;
    publish({ busy, error: '', ...(busy === 'candidates' ? {} : { notice: '' }) });
    try { await work(token, captured); }
    catch (failure) {
      if (current(token)) publish({ error: message(failure) });
      else console.warn('已过期的只读参考请求未完成。', message(failure));
    } finally {
      if (current(token)) {
        publish({ busy: null });
        if (refreshRequested && compareReady) {
          refreshRequested = false;
          if (snapshot.selection) {
            const { sourceId, category, name } = snapshot.selection;
            void compare(sourceId, category, name, false);
          }
        }
      }
    }
  }
  async function cleanUnused(token: number) {
    for (const [id, value] of owned) {
      if (!current(token)) return;
      if (id === snapshot.selection?.sourceId || id === snapshot.pending?.sourceId) continue;
      await release(value);
      if (current(token)) publish({ sources: snapshot.sources.filter(source => source.sourceId !== id) });
    }
  }
  async function compare(sourceId: string, category: string, name: string, commit = true) {
    return run('compare', async (token, captured) => {
      const expectedPath = path, expectedRevision = revision, expectedSession = snapshot.sessionId;
      const value = await captured.onCompare(sourceId, category, name);
      if (!current(token)) return;
      if (value.sessionId !== expectedSession || value.currentPath !== expectedPath || value.revision !== expectedRevision
          || value.sourceId !== sourceId || value.category !== category || value.name !== name) {
        throw new Error('参考结果与当前会话、文件或版本不一致，请重新比较。');
      }
      // Commit the successful selection before disposing of old resources. A
      // cleanup failure is recoverable and does not pretend the new read failed.
      publish({ comparison: value, stale: false, notice: '已更新只读对比。',
        ...(commit ? { selection: { sourceId, category, name }, pending: null } : {}) });
      if (commit) await cleanUnused(token);
    });
  }
  async function loadSources() {
    return run('sources', async (token, captured) => {
      const value = await captured.onSources();
      if (!current(token)) return;
      for (const source of value.sources) {
        if (source.kind !== 'vanilla' && !owned.has(source.sourceId)) owned.set(source.sourceId, { source, actions: captured });
      }
      publish({ sources: value.sources });
    });
  }
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start(sessionId: string, currentPath: string, currentRevision: number, callbacks: ComparisonCallbacks) {
      stop(); active = true; compareReady = true; path = currentPath; revision = currentRevision; actions = callbacks;
      publish({ ...initial(), sessionId });
    },
    stop,
    loadSources,
    updateContext(currentPath: string, currentRevision: number, callbacks: ComparisonCallbacks, ready = true) {
      actions = callbacks;
      const becameReady = ready && !compareReady;
      compareReady = ready;
      if (!active) return;
      if (path === currentPath && revision === currentRevision) {
        if (becameReady && refreshRequested && !snapshot.busy) {
          refreshRequested = false;
          if (snapshot.selection) {
            const { sourceId, category, name } = snapshot.selection;
            void compare(sourceId, category, name, false);
          }
        }
        return;
      }
      path = currentPath; revision = currentRevision;
      // Native selection, candidate reads and releases belong to the session,
      // not the document revision. Let them settle before refreshing the table.
      if (snapshot.busy && snapshot.busy !== 'compare') {
        refreshRequested = true;
        publish({ stale: Boolean(snapshot.comparison) }); return;
      }
      serial++;
      publish({ busy: null, stale: Boolean(snapshot.comparison), error: '', notice: '' });
      if (!compareReady) { refreshRequested = Boolean(snapshot.selection); return; }
      refreshRequested = false;
      if (snapshot.selection) {
        const { sourceId, category, name } = snapshot.selection;
        void compare(sourceId, category, name, false);
      } else if (!snapshot.sources.length) void loadSources();
    },
    async open(kind: 'folder' | 'zip') {
      if (snapshot.pending) { publish({ error: '请先确认或取消待选参考。' }); return; }
      return run('open', async (token, captured) => {
        const source = await captured.onOpen(kind);
        if (!source) { if (current(token)) publish({ notice: '已取消选择，原对比保持不变。' }); return; }
        const value: Owned = { source, actions: captured };
        if (!current(token)) { await releaseDetached(value); return; }
        if (source.kind === 'vanilla') throw new Error('导入来源类型无效，请重新选择。');
        owned.set(source.sourceId, value);
        publish({ pending: source, sources: [...snapshot.sources.filter(item => item.sourceId !== source.sourceId), source],
          page: null, notice: '请选择参考内容；确认比较前保留原对比。' });
      });
    },
    async candidates(sourceId: string, category: string, query: string, offset = 0) {
      return run('candidates', async (token, captured) => {
        publish({ page: null });
        const page = await captured.onCandidates(sourceId, category, query, offset);
        if (!current(token)) return;
        if (page.sourceId !== sourceId || page.category !== category || page.offset !== offset) {
          throw new Error('候选来源不一致，请重新搜索。');
        }
        publish({ page });
      });
    },
    compare,
    async cancelPending() {
      const pending = snapshot.pending;
      if (!pending) return;
      return run('cancel', async token => {
        const value = owned.get(pending.sourceId);
        if (value) await release(value);
        if (current(token)) publish({ pending: null, sources: snapshot.sources.filter(source => source.sourceId !== pending.sourceId),
          page: null, notice: '已取消待选参考，原对比保持不变。' });
      });
    },
    async retryCleanup() { return run('cleanup', cleanUnused); },
    async refresh() {
      if (!snapshot.selection) return loadSources();
      const { sourceId, category, name } = snapshot.selection;
      return compare(sourceId, category, name, false);
    },
  };
}
