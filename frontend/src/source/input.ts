export const SOURCE_DRAFT_FIELD = '$source';

export interface SourceInputCallbacks {
  onDraft(text: string): void;
  onCommit(): Promise<void>;
  onComposition(active: boolean): void;
}

/** Timing only. Text, parse errors and history belong to the existing draft/session stores. */
export function createSourceInput(callbacks: SourceInputCallbacks) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let dirty = false;
  let composing = false;
  let disposed = false;
  let enabled = true;
  let version = 0;
  let pending: Promise<void> | undefined;
  function cancel() { clearTimeout(timer); timer = undefined; }
  function schedule() {
    cancel();
    if (!disposed && enabled && !composing && !pending && dirty) timer = setTimeout(() => { void flush().catch(() => {}); }, 500);
  }
  async function flush() {
    cancel();
    if (disposed || !enabled) return;
    if (composing) throw new Error('请结束中文输入后再提交。');
    if (pending) return pending;
    if (!dirty) return;
    const submitted = version;
    pending = callbacks.onCommit().then(() => {
      if (submitted === version) dirty = false;
    }).finally(() => {
      pending = undefined;
      if (submitted !== version) schedule();
    });
    return pending;
  }
  return {
    change(text: string) {
      if (disposed || !enabled) return;
      version++; callbacks.onDraft(text); dirty = true; schedule();
    },
    composition(active: boolean) {
      if (disposed || active === composing) return;
      composing = active; callbacks.onComposition(active); schedule();
    },
    setEnabled(value: boolean) { if (enabled !== value) { enabled = value; schedule(); } },
    cancelScheduled: cancel,
    flush,
    dispose() {
      if (disposed) return;
      disposed = true; cancel();
      if (composing) { composing = false; callbacks.onComposition(false); }
    },
  };
}
