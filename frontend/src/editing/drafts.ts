import type { FormDrafts, FormErrors } from '../forms/types';

interface DraftSnapshot {
  drafts: Record<string, FormDrafts>;
  errors: Record<string, FormErrors>;
  composing: boolean;
}

/** Input buffers only: Python owns parsing, valid data and history. */
export function createDraftStore(submit: (path: string, field: string, text: string) => Promise<void>) {
  let snapshot: DraftSnapshot = { drafts: {}, errors: {}, composing: false };
  let generation = 0;
  let tail: Promise<void> = Promise.resolve();
  const compositions = new Set<string>();
  const listeners = new Set<() => void>();
  const key = (path: string, field: string) => JSON.stringify([path, field]);
  const publish = () => { snapshot = { ...snapshot, composing: compositions.size > 0 }; listeners.forEach(listener => listener()); };
  function without<T>(records: Record<string, Record<string, T>>, path: string, field: string) {
    const result = { ...records }, document = { ...result[path] };
    delete document[field];
    if (Object.keys(document).length) result[path] = document;
    else delete result[path];
    return result;
  }
  function resetField(path: string, field: string) {
    snapshot = { ...snapshot, drafts: without(snapshot.drafts, path, field), errors: without(snapshot.errors, path, field) };
    compositions.delete(key(path, field)); publish();
  }
  async function commitField(path: string, field: string, current: number) {
    if (current !== generation || !(field in (snapshot.drafts[path] ?? {}))) return;
    if (compositions.has(key(path, field))) throw new Error('请结束中文输入后再提交。');
    const text = snapshot.drafts[path][field];
    try {
      await submit(path, field, text);
      if (current === generation && snapshot.drafts[path]?.[field] === text) resetField(path, field);
    } catch (error) {
      if (current === generation && snapshot.drafts[path]?.[field] === text) {
        snapshot = { ...snapshot, errors: { ...snapshot.errors, [path]: { ...snapshot.errors[path],
          [field]: error instanceof Error ? error.message : '输入未能保存，请重试。' } } };
        publish();
      }
      throw error;
    }
  }
  function enqueue(operation: (current: number) => Promise<void>) {
    const current = generation;
    const job = tail.then(() => { if (current === generation) return operation(current); });
    tail = job.catch(() => {});
    return job;
  }
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    set(path: string, field: string, text: string) {
      snapshot = { ...snapshot, drafts: { ...snapshot.drafts, [path]: { ...snapshot.drafts[path], [field]: text } },
        errors: without(snapshot.errors, path, field) }; publish();
    },
    composition(path: string, field: string, active: boolean) {
      if (active) compositions.add(key(path, field)); else compositions.delete(key(path, field)); publish();
    },
    resetField,
    removePaths(paths: string[]) {
      const drafts = { ...snapshot.drafts }, errors = { ...snapshot.errors };
      for (const path of paths) { delete drafts[path]; delete errors[path]; }
      for (const item of compositions) if (paths.includes(JSON.parse(item)[0])) compositions.delete(item);
      snapshot = { drafts, errors, composing: compositions.size > 0 }; publish();
    },
    reset() {
      generation++; tail = Promise.resolve(); compositions.clear(); snapshot = { drafts: {}, errors: {}, composing: false }; publish();
    },
    settled: () => tail,
    commit: (path: string, field: string) => enqueue(current => commitField(path, field, current)),
    flush: (omit?: { path: string; field: string }) => enqueue(async current => {
      if (compositions.size) throw new Error('请结束中文输入后再保存。');
      for (const [path, fields] of Object.entries(snapshot.drafts)) {
        for (const field of Object.keys(fields)) {
          if (omit?.path !== path || omit.field !== field) await commitField(path, field, current);
        }
      }
    }),
  };
}
