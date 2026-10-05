import type { ContentAction, ContentDialog, ContentForm, ContentToolsProps, ContentToolsSnapshot } from './types';

const emptyForm = (): ContentForm => ({ category: '', kind: '', name: '', modId: '', displayName: '', author: '' });

/** Dialog buffers only. The host owns commands, project identity and persistence. */
export function createContentToolsState(callbacks: Pick<ContentToolsProps, 'loadCatalogue' | 'onAction'>) {
  let snapshot: ContentToolsSnapshot = { sessionId: null, mode: null, targetPath: null,
    catalogue: null, loading: false, submitting: false, error: '', conflict: false, form: emptyForm() };
  let generation = 0;
  const listeners = new Set<() => void>();
  const publish = (patch: Partial<ContentToolsSnapshot>) => {
    snapshot = { ...snapshot, ...patch }; listeners.forEach(listener => listener());
  };
  async function reload() {
    if (!snapshot.mode || snapshot.mode === 'delete_content' || snapshot.submitting) return;
    const current = ++generation;
    publish({ loading: true, error: '' });
    try {
      const catalogue = await callbacks.loadCatalogue();
      if (current !== generation) return;
      const category = catalogue.categories.find(item => item.id === snapshot.form.category)
        ?? catalogue.categories.find(item => item.templates.length);
      const kind = category?.templates.some(item => item.kind === snapshot.form.kind)
        ? snapshot.form.kind : category?.templates[0]?.kind ?? '';
      publish({ catalogue, loading: false, form: { ...snapshot.form, category: category?.id ?? '', kind } });
    } catch (error) {
      if (current === generation) publish({ loading: false, error: error instanceof Error ? error.message : '内容选项读取失败，请重试。' });
    }
  }
  async function perform(action: ContentAction, payload: Record<string, unknown>) {
    const current = generation;
    publish({ submitting: true, error: '' });
    try {
      await callbacks.onAction(action, payload);
      if (current === generation) publish({ mode: null, submitting: false, conflict: false });
    } catch (error) {
      if (current !== generation) return;
      const code = typeof error === 'object' && error !== null && 'code' in error ? error.code : undefined;
      publish({ submitting: false, error: error instanceof Error ? error.message : '操作失败，请重试。',
        conflict: action === 'create_content' && code === 'FILE_EXISTS' });
    }
  }
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    dispose() { generation++; },
    complete() {
      generation++; publish({ mode: null, loading: false, submitting: false, error: '', conflict: false });
    },
    reload,
    session(sessionId: string | null) {
      generation++;
      publish({ sessionId, mode: null, targetPath: null, catalogue: null, loading: false,
        submitting: false, error: '', conflict: false, form: emptyForm() });
    },
    async open(mode: ContentDialog, path: string | null) {
      if (snapshot.submitting) return;
      generation++;
      publish({ mode, targetPath: path, catalogue: null, loading: false, error: '', conflict: false,
        form: { ...emptyForm(), name: mode === 'rename_content' && path ? path.split('/').at(-1)!.replace(/\.json$/, '') : '' } });
      await reload();
    },
    update(field: keyof ContentForm, value: string) {
      if (snapshot.submitting) return;
      const form = { ...snapshot.form, [field]: value };
      if (field === 'category') form.kind = snapshot.catalogue?.categories.find(category => category.id === value)?.templates[0]?.kind ?? '';
      publish({ form, conflict: false, error: '' });
    },
    cancel() {
      if (snapshot.submitting) return;
      generation++; publish({ mode: null, loading: false, error: '', conflict: false });
    },
    async submit(overwrite = false) {
      const { mode, form, targetPath } = snapshot;
      if (!mode || snapshot.submitting || snapshot.loading || (overwrite && (!snapshot.conflict || mode !== 'create_content'))) return;
      if (mode !== 'delete_content' && !snapshot.catalogue) return;
      if (mode === 'create_content') {
        if (!snapshot.catalogue || !form.name.trim() || !form.category || !form.kind) return;
        await perform(mode, { category: form.category, kind: form.kind, name: form.name.trim(), overwrite });
      } else if (mode === 'rename_content') {
        if (!targetPath || !form.name.trim()) return;
        await perform(mode, { path: targetPath, newName: form.name.trim() });
      } else if (mode === 'delete_content') {
        if (targetPath) await perform(mode, { path: targetPath, confirmed: true });
      } else {
        if (!form.modId.trim()) return;
        await perform(mode, { mod_id: form.modId.trim(), displayName: form.displayName, author: form.author });
      }
    },
    async reveal(path: string | null) {
      if (!path || snapshot.submitting || snapshot.mode) return;
      await perform('reveal_content', { path });
    },
  };
}
