import type { GenerationCallbacks, GenerationCandidate, GenerationOutput } from './types';

interface Snapshot {
  identity: string;
  candidate: GenerationCandidate | null;
  busy: 'preview' | 'confirm' | 'cancel' | null;
  error: string;
  confirmed: boolean;
}
interface Owned { candidate: GenerationCandidate; callbacks: GenerationCallbacks; release?: Promise<void> }

/** Candidate lifetimes only. PNG generation, file writes and history stay in Python. */
export function createGenerationController() {
  let snapshot: Snapshot = { identity: '', candidate: null, busy: null, error: '', confirmed: false };
  let generation = 0, active = false, session = '';
  let callbacks: GenerationCallbacks;
  let owned: Owned | null = null;
  const listeners = new Set<() => void>();
  const publish = (update: Partial<Snapshot>) => { snapshot = { ...snapshot, ...update }; listeners.forEach(listener => listener()); };
  const message = (failure: unknown) => failure instanceof Error ? failure.message : '贴图生成操作未完成，请重试。';
  const current = (token: number) => active && generation === token;
  async function release(value: Owned) {
    if (!value.release) value.release = Promise.resolve().then(() => value.callbacks.onCancel(value.candidate.candidateId));
    try { await value.release; } catch (failure) { value.release = undefined; throw failure; }
  }
  const releaseDetached = (value: Owned) => release(value).catch(failure => { console.warn('生成候选清理失败，工程关闭时将统一释放。', message(failure)); });
  function stop() {
    active = false; generation++;
    const previous = owned; owned = null;
    // Confirmation owns the candidate until it settles; cancelling ahead of a
    // queued confirm could invalidate a legitimate write.
    if (previous && snapshot.busy !== 'confirm') void releaseDetached(previous);
  }
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start(identity: string, sessionId: string, actions: GenerationCallbacks) {
      stop(); active = true; session = sessionId; callbacks = actions;
      publish({ identity, candidate: null, busy: null, error: '', confirmed: false });
    },
    stop,
    async preview(outputs: GenerationOutput[]) {
      if (!active || snapshot.busy || owned) return;
      const token = generation, actions = callbacks, expectedSession = session;
      publish({ busy: 'preview', error: '', confirmed: false });
      try {
        const candidate = await actions.onPreview(outputs);
        const value: Owned = { candidate, callbacks: actions };
        if (!current(token)) { await releaseDetached(value); return; }
        if (candidate.sessionId !== expectedSession) {
          await releaseDetached(value); throw new Error('生成候选属于其他会话，请重新预览。');
        }
        owned = value; publish({ candidate });
      } catch (failure) { if (current(token)) publish({ error: message(failure) }); }
      finally { if (current(token)) publish({ busy: null }); }
    },
    async confirm(overwrite: boolean) {
      if (!active || snapshot.busy || !owned) return;
      if (owned.candidate.outputs.some(output => output.exists) && !overwrite) {
        publish({ error: '请明确确认覆盖已有贴图。' }); return;
      }
      const token = generation, value = owned;
      publish({ busy: 'confirm', error: '' });
      try {
        await value.callbacks.onConfirm(value.candidate.candidateId, overwrite);
        if (current(token)) { owned = null; publish({ candidate: null, confirmed: true }); }
      } catch (failure) {
        if (current(token)) publish({ error: message(failure) });
        else await releaseDetached(value);
      } finally { if (current(token)) publish({ busy: null }); }
    },
    async cancel() {
      if (!active || snapshot.busy || !owned) return;
      const token = generation, value = owned;
      publish({ busy: 'cancel', error: '' });
      try {
        await release(value);
        if (current(token)) { owned = null; publish({ candidate: null, confirmed: false }); }
      } catch (failure) { if (current(token)) publish({ error: message(failure) }); }
      finally { if (current(token)) publish({ busy: null }); }
    },
  };
}
