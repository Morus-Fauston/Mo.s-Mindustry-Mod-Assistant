import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { desktop, DesktopError } from '../bridge/desktop';
import { createEditingClient, uncertainResult } from '../editing/client';
import type { DocumentSnapshot, EditingState } from '../workspace/types';
import type { SpriteTargets } from '../resources/types';
import { SpriteGeneration } from './SpriteGeneration';
import type { GenerationCallbacks, GenerationCandidate } from './types';
import styles from './SpriteGeneration.module.css';

export interface GenerationOwner {
  sessionId: string; path: string; revision: number; resourceRevision: number;
  disabled: boolean; hasDrafts: boolean;
}
export interface GenerationSectionProps {
  document: DocumentSnapshot;
  resourceRevision: number;
  disabled: boolean;
  hasDrafts: boolean;
  editing: ReturnType<typeof createEditingClient>;
}
const identity = (owner: GenerationOwner) => JSON.stringify([owner.sessionId, owner.path, owner.revision, owner.resourceRevision]);
const scope = (owner: GenerationOwner) => JSON.stringify([owner.sessionId, owner.path]);
const message = (error: unknown) => error instanceof Error ? error.message : '贴图生成操作未完成。';
interface GenerationResult { state: EditingState; candidate?: GenerationCandidate }

/** Transport adaptation only. The existing SpriteGeneration controller owns normal candidates. */
export function createGenerationBridge(editing: ReturnType<typeof createEditingClient>, currentOwner: () => GenerationOwner | null,
  cancel: (sessionId: string, candidateId: string) => Promise<void>,
  notify: (message: string, owner: GenerationOwner, failed?: boolean) => void) {
  let active = true;
  const failedCleanups = new Map<string, { candidate: GenerationCandidate; owner: GenerationOwner }>();
  const pendingCleanups = new Map<string, Promise<void>>();
  const recoveryChecks = new Set<() => void>();
  function notice(text: string, owner: GenerationOwner, failed = false) {
    const current = currentOwner();
    if (active && current && scope(current) === scope(owner)) notify(text, owner, failed);
  }
  function releaseRecovered(candidate: GenerationCandidate, owner: GenerationOwner): Promise<void> {
    const existing = pendingCleanups.get(candidate.candidateId);
    if (existing) return existing;
    const release = Promise.resolve().then(() => cancel(owner.sessionId, candidate.candidateId)).then(() => {
      failedCleanups.delete(candidate.candidateId);
      notice('已取回并释放原预览，请重新预览。', owner);
    }).catch(error => {
      failedCleanups.set(candidate.candidateId, { candidate, owner });
      notice(`原预览已取回，但候选清理失败：${message(error)} 请重试清理或关闭工程。`, owner, true);
    }).finally(() => { pendingCleanups.delete(candidate.candidateId); });
    pendingCleanups.set(candidate.candidateId, release);
    return release;
  }
  function guard(owner: GenerationOwner) {
    const current = currentOwner(), snapshot = editing.getSnapshot();
    if (!active || !current || identity(current) !== identity(owner) || snapshot.state?.sessionId !== owner.sessionId) {
      throw new DesktopError('STALE_SESSION', '生成内容已经切换，请重新预览。');
    }
    if (current.hasDrafts) throw new Error('请先提交或修正当前字段，再生成贴图。');
    for (const [id, cleanup] of failedCleanups) if (cleanup.owner.sessionId !== owner.sessionId) failedCleanups.delete(id);
    if (current.disabled || snapshot.busy || snapshot.uncertain || failedCleanups.size || pendingCleanups.size) throw new Error('请先完成当前操作或清理原预览，再生成贴图。');
  }
  return {
    setActive(value: boolean) { active = value; },
    observeResult() { for (const check of [...recoveryChecks]) check(); },
    async retryCleanup() {
      for (const { candidate, owner } of [...failedCleanups.values()]) await releaseRecovered(candidate, owner);
    },
    callbacks(owner: GenerationOwner): GenerationCallbacks {
      return {
        async onPreview(outputs) {
          guard(owner);
          const previous = editing.getSnapshot().result;
          let abandoned = false;
          let unsubscribe = () => {};
          const observe = () => {
            const snapshot = editing.getSnapshot();
            if (snapshot.state?.sessionId !== owner.sessionId) { unsubscribe(); return; }
            if (!abandoned || snapshot.busy || snapshot.uncertain) return;
            const result = snapshot.result;
            unsubscribe();
            if (result !== previous && result?.action === 'preview_generation') {
              const data = result.data as GenerationResult;
              if (data.candidate?.sessionId === owner.sessionId) { void releaseRecovered(data.candidate, owner); return; }
            }
            notice('原预览结果已不可恢复，请关闭工程释放候选后重新打开。', owner, true);
          };
          const stopSubscription = editing.subscribe(observe);
          recoveryChecks.add(observe);
          unsubscribe = () => { stopSubscription(); recoveryChecks.delete(observe); };
          try {
            await editing.run('preview_generation', { path: owner.path, outputs });
            const result = editing.getSnapshot().result;
            const data = result?.data as GenerationResult | undefined;
            if (result === previous || result?.action !== 'preview_generation' || data?.candidate?.sessionId !== owner.sessionId
              || typeof data.candidate.candidateId !== 'string' || !Array.isArray(data.candidate.outputs)) {
              throw new DesktopError('INVALID_RESPONSE', '生成预览结果无效，请查询原操作结果。');
            }
            // Returning even after unmount lets the old candidate controller release through its captured session.
            unsubscribe();
            return data.candidate;
          } catch (error) {
            if (uncertainResult(error) && editing.getSnapshot().uncertain) { abandoned = true; observe(); }
            else unsubscribe();
            throw error;
          }
        },
        async onConfirm(candidateId, overwrite) {
          guard(owner);
          const previous = editing.getSnapshot().result;
          await editing.run('confirm_generation', { candidateId, overwrite });
          const snapshot = editing.getSnapshot(), result = snapshot.result;
          const data = result?.data as GenerationResult | undefined;
          if (result === previous || result?.action !== 'confirm_generation' || data?.state.sessionId !== owner.sessionId) {
            throw new DesktopError('INVALID_RESPONSE', '生成确认结果无效，请查询原操作结果。');
          }
          notice('贴图已写入工程，可通过撤销恢复。', owner);
        },
        onCancel: candidateId => cancel(owner.sessionId, candidateId),
      };
    },
  };
}

export function GenerationSection(props: GenerationSectionProps) {
  const { document, editing } = props;
  const owner: GenerationOwner = { sessionId: document.sessionId, path: document.path, revision: document.revision,
    resourceRevision: props.resourceRevision, disabled: props.disabled || document.validData === false, hasDrafts: props.hasDrafts };
  const ownerRef = useRef<GenerationOwner>(owner); ownerRef.current = owner;
  const mounted = useRef(true);
  const [notice, setNotice] = useState<{ owner: string; message: string; failed: boolean } | null>(null);
  const [bridge] = useState(() => createGenerationBridge(editing, () => mounted.current ? ownerRef.current : null,
    async (sessionId, candidateId) => {
      try { await desktop.request('cancel_generation', { candidateId }, sessionId); }
      catch (error) { if (!(error instanceof DesktopError && ['STALE_SESSION', 'NO_PROJECT'].includes(error.code))) throw error; }
    }, (text, previousOwner, failed = false) => setNotice({ owner: scope(previousOwner), message: text, failed })));
  const editor = useSyncExternalStore(editing.subscribe, editing.getSnapshot);
  // Keep the authoritative operation result subscribed even if only recovery updated it.
  const result = editor.result;
  const key = identity(owner), ownerScope = scope(owner);
  const [targets, setTargets] = useState<{ identity: string; value: SpriteTargets } | null>(null);
  const [readError, setReadError] = useState<{ identity: string; message: string } | null>(null);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    mounted.current = true; bridge.setActive(true);
    return () => { mounted.current = false; bridge.setActive(false); };
  }, [bridge]);
  useEffect(() => {
    let alive = true;
    if (document.validData === false) return;
    setReadError(null);
    void desktop.request<SpriteTargets>('sprite_targets', { path: document.path }, document.sessionId)
      .then(value => { if (alive) setTargets({ identity: key, value }); })
      .catch(error => { if (alive) setReadError({ identity: key, message: message(error) }); });
    return () => { alive = false; };
  }, [key, retry, document.validData]);
  useEffect(() => { bridge.observeResult(); }, [bridge, result, editor.busy, editor.uncertain]);
  const currentTargets = targets?.identity === key ? targets.value.targets : null;
  const error = readError?.identity === key ? readError.message : '';
  return <>
    {props.hasDrafts && <p className={styles.status} role="status">请先提交或修正当前字段，再生成贴图。</p>}
    {notice?.owner === ownerScope && <p className={notice.failed ? styles.error : styles.status} role={notice.failed ? 'alert' : 'status'}>{notice.message}
      {notice.failed && <button type="button" className={styles.action} onClick={() => void bridge.retryCleanup()}>重试清理候选</button>}</p>}
    {error ? <p className={styles.error} role="alert">{error} <button type="button" className={styles.action} onClick={() => setRetry(value => value + 1)}>重试读取生成目标</button></p>
      : document.validData === false ? <p className={styles.status}>源码尚未解析，无法生成贴图。</p>
      : !currentTargets ? <p className={styles.status} role="status">正在读取生成目标…</p>
      : <SpriteGeneration key={key} sessionId={document.sessionId} path={document.path} revision={document.revision}
        disabled={owner.disabled || owner.hasDrafts || editor.busy || editor.uncertain} targets={currentTargets}
        fieldNames={document.fieldNames} fieldDocs={document.fieldDocs} {...bridge.callbacks(owner)} />}
  </>;
}
