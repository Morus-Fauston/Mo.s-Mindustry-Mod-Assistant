import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react';
import { desktop, DesktopError } from '../bridge/desktop';
import { createEditingClient, uncertainResult } from '../editing/client';
import type { DocumentSnapshot, EditingState } from '../workspace/types';
import { ReferenceComparison } from './ReferenceComparison';
import type { CandidatePage, Comparison, ComparisonCallbacks, SourceDescriptor } from './types';
import styles from './ReferenceComparison.module.css';

export interface ComparisonOwner {
  sessionId: string; path: string; revision: number; disabled: boolean; hasDrafts: boolean;
}
export interface ComparisonSectionProps {
  document: DocumentSnapshot;
  disabled: boolean;
  hasDrafts: boolean;
  editing: ReturnType<typeof createEditingClient>;
}
type ReadRequest = <T>(action: string, payload: Record<string, unknown>, sessionId: string) => Promise<T>;
interface OpenResult { state: EditingState; source: SourceDescriptor | null }
const message = (error: unknown) => error instanceof Error ? error.message : '参考操作未完成。';
const validSource = (source: unknown): source is SourceDescriptor => {
  if (!source || typeof source !== 'object') return false;
  const value = source as SourceDescriptor;
  return typeof value.sourceId === 'string' && Boolean(value.sourceId) && ['folder', 'zip'].includes(value.kind)
    && typeof value.label === 'string' && Array.isArray(value.categories) && Array.isArray(value.warnings);
};

/** Transport only: the existing controller owns accepted sources and Python owns current data. */
export function createComparisonBridge(editing: ReturnType<typeof createEditingClient>, currentOwner: () => ComparisonOwner | null,
  request: ReadRequest, notify: (message: string, owner: ComparisonOwner, failed?: boolean, retryCleanup?: boolean) => void) {
  let active = true, blockedSession: string | null = null;
  const failedCleanups = new Map<string, { source: SourceDescriptor; owner: ComparisonOwner }>();
  const pendingCleanups = new Map<string, { owner: ComparisonOwner; promise: Promise<void> }>();
  const recoveryChecks = new Set<() => void>();
  function notice(text: string, owner: ComparisonOwner, failed = false, retryCleanup = false) {
    if (active && currentOwner()?.sessionId === owner.sessionId) notify(text, owner, failed, retryCleanup);
  }
  async function release(sessionId: string, sourceId: string) {
    try {
      const result = await request<{ released: boolean }>('release_reference', { sourceId }, sessionId);
      if (result?.released !== true) throw new DesktopError('INVALID_RESPONSE', '参考来源释放结果无效，请重试清理。');
    }
    catch (error) { if (!(error instanceof DesktopError && ['STALE_SESSION', 'NO_PROJECT'].includes(error.code))) throw error; }
  }
  function releaseRecovered(source: SourceDescriptor, owner: ComparisonOwner) {
    const key = JSON.stringify([owner.sessionId, source.sourceId]);
    const existing = pendingCleanups.get(key);
    if (existing) return existing.promise;
    const pending = Promise.resolve().then(() => release(owner.sessionId, source.sourceId)).then(() => {
      failedCleanups.delete(key);
      notice('已取回并释放原参考来源，请重新选择。', owner);
    }).catch(error => {
      failedCleanups.set(key, { source, owner });
      notice(`参考来源已取回，但清理失败：${message(error)} 请重试清理或关闭工程。`, owner, true, true);
    }).finally(() => { pendingCleanups.delete(key); });
    pendingCleanups.set(key, { owner, promise: pending });
    return pending;
  }
  function guard(owner: ComparisonOwner, operation: 'read' | 'open' | 'compare') {
    const current = currentOwner(), snapshot = editing.getSnapshot();
    if (!active || !current || current.sessionId !== owner.sessionId || snapshot.state?.sessionId !== owner.sessionId) {
      throw new DesktopError('STALE_SESSION', '工程已经切换，请重新读取参考。');
    }
    if (operation === 'read') return;
    if (operation === 'compare') {
      if (current.path !== owner.path || current.revision !== owner.revision || snapshot.state.revision !== owner.revision) {
        throw new DesktopError('STALE_REVISION', '当前内容已经变化，请重新比较。');
      }
      if (current.hasDrafts) throw new Error('请先提交或修正当前字段，再比较参考内容。');
    }
    if (blockedSession === owner.sessionId) throw new Error('原参考结果不可恢复，请关闭工程释放来源后重新打开。');
    for (const [key, cleanup] of failedCleanups) if (cleanup.owner.sessionId !== owner.sessionId) failedCleanups.delete(key);
    const cleaning = [...pendingCleanups.values()].some(cleanup => cleanup.owner.sessionId === owner.sessionId);
    if (current.disabled || snapshot.busy || snapshot.uncertain || failedCleanups.size || cleaning) {
      throw new Error('请先完成当前操作或清理原参考来源，再继续。');
    }
  }
  return {
    setActive(value: boolean) { active = value; },
    observeResult() { for (const check of [...recoveryChecks]) check(); },
    async retryCleanup() { for (const { source, owner } of [...failedCleanups.values()]) await releaseRecovered(source, owner); },
    callbacks(owner: ComparisonOwner): ComparisonCallbacks {
      return {
        async onSources() {
          guard(owner, 'read');
          return request<{ sources: SourceDescriptor[] }>('reference_sources', {}, owner.sessionId);
        },
        async onCandidates(sourceId, category, query, offset = 0) {
          guard(owner, 'read');
          return request<CandidatePage>('reference_candidates_for_compare', { sourceId, category, query, offset }, owner.sessionId);
        },
        async onCompare(sourceId, category, name) {
          guard(owner, 'compare');
          return request<Comparison>('compare_reference', { sourceId, category, name, path: owner.path,
            expectedRevision: owner.revision }, owner.sessionId);
        },
        async onOpen(kind) {
          guard(owner, 'open');
          const previous = editing.getSnapshot().result;
          let abandoned = false, unsubscribe = () => {};
          const observe = () => {
            const snapshot = editing.getSnapshot();
            if (snapshot.state?.sessionId !== owner.sessionId) { unsubscribe(); return; }
            if (!abandoned || snapshot.busy) return;
            if (snapshot.uncertain) {
              notice('打开结果尚未确认，请继续查询原操作结果；若始终未知，请先另行记录未保存内容，再重新启动程序。', owner);
              return;
            }
            unsubscribe();
            const result = snapshot.result, data = result?.data as OpenResult | undefined;
            if (result !== previous && result?.action === 'open_reference' && data?.state?.sessionId === owner.sessionId) {
              if (data.source === null) { notice('原参考选择已取消，可以重新选择。', owner); return; }
              if (validSource(data.source)) { void releaseRecovered(data.source, owner); return; }
            }
            blockedSession = owner.sessionId;
            notice('原参考结果已不可恢复，请关闭工程释放来源后重新打开。', owner, true);
          };
          const stopSubscription = editing.subscribe(observe);
          recoveryChecks.add(observe);
          unsubscribe = () => { stopSubscription(); recoveryChecks.delete(observe); };
          try {
            await editing.run('open_reference', { kind });
            const result = editing.getSnapshot().result, data = result?.data as OpenResult | undefined;
            if (result === previous || result?.action !== 'open_reference' || data?.state?.sessionId !== owner.sessionId
              || data.source !== null && !validSource(data.source)) {
              blockedSession = owner.sessionId;
              notice('参考来源返回资料无效，请关闭工程释放来源后重新打开。', owner, true);
              throw new DesktopError('INVALID_RESPONSE', '参考来源返回资料无效。');
            }
            unsubscribe();
            // An unmounted controller releases a normal late response through captured callbacks.
            return data.source;
          } catch (error) {
            if (uncertainResult(error) && editing.getSnapshot().uncertain) { abandoned = true; observe(); }
            else unsubscribe();
            throw error;
          }
        },
        onRelease: sourceId => release(owner.sessionId, sourceId),
      };
    },
  };
}

export function ComparisonSection({ document, disabled, hasDrafts, editing }: ComparisonSectionProps) {
  const owner: ComparisonOwner = { sessionId: document.sessionId, path: document.path, revision: document.revision,
    disabled: disabled || document.validData === false, hasDrafts };
  const ownerRef = useRef(owner); ownerRef.current = owner;
  const mounted = useRef(true);
  const [notice, setNotice] = useState<{ sessionId: string; text: string; failed: boolean; retryCleanup: boolean } | null>(null);
  const [bridge] = useState(() => createComparisonBridge(editing, () => mounted.current ? ownerRef.current : null,
    (action, payload, sessionId) => desktop.request(action, payload, sessionId),
    (text, previous, failed = false, retryCleanup = false) => setNotice({ sessionId: previous.sessionId, text, failed, retryCleanup })));
  const editor = useSyncExternalStore(editing.subscribe, editing.getSnapshot);
  useLayoutEffect(() => {
    mounted.current = true; bridge.setActive(true);
    return () => { mounted.current = false; bridge.setActive(false); };
  }, [bridge]);
  useEffect(() => { bridge.observeResult(); }, [bridge, editor.result, editor.busy, editor.uncertain]);
  return <>
    {hasDrafts && <p className={styles.status} role="status">请先提交或修正当前字段，再比较参考内容。</p>}
    {notice?.sessionId === document.sessionId && <p className={notice.failed ? styles.error : styles.status}
      role={notice.failed ? 'alert' : 'status'}>{notice.text}
      {notice.retryCleanup && <button type="button" className={styles.action} onClick={() => void bridge.retryCleanup()}>重试清理参考来源</button>}</p>}
    <ReferenceComparison sessionId={document.sessionId} path={document.path} revision={document.revision}
      fieldNames={document.fieldNames} fieldDocs={document.fieldDocs}
      disabled={owner.disabled || editor.busy || editor.uncertain} compareDisabled={hasDrafts} {...bridge.callbacks(owner)} />
  </>;
}
