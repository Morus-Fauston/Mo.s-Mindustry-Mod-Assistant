import type { EditablePreferences, PreferenceKey, PreferencesPatch, PreferencesState } from './types';

export const editablePreferenceKeys: PreferenceKey[] = ['theme', 'display_name_mode', 'auto_save_interval', 'sprite_zoom'];
type Drafts = Partial<Record<PreferenceKey, string>>;
export interface PreferencesDraftSnapshot {
  drafts: Drafts;
  text: Record<PreferenceKey, string>;
  errors: Drafts;
  dirty: boolean;
  pending: boolean;
  error: string;
}

function parse(key: PreferenceKey, text: string): EditablePreferences[PreferenceKey] | null {
  if (key === 'theme') return text === 'light' || text === 'dark' ? text : null;
  if (key === 'display_name_mode') return ['zh_en', 'en_zh', 'zh', 'en'].includes(text) ? text as EditablePreferences['display_name_mode'] : null;
  if (!/^\d+$/.test(text.trim())) return null;
  const value = Number(text.trim());
  return Number.isSafeInteger(value) && value >= (key === 'auto_save_interval' ? 0 : 1)
    && value <= (key === 'auto_save_interval' ? 3600 : 8) ? value : null;
}
const invalidMessage = (key: PreferenceKey) => key === 'auto_save_interval' ? '请输入 0 至 3600 的整数；0 表示关闭自动保存。'
  : key === 'sprite_zoom' ? '请输入 1 至 8 的整数。' : '请选择列表中的有效选项。';

/** Only settings input buffers. Persistence, revision checks and transport recovery belong to the parent. */
export function createPreferencesDrafts(initial: PreferencesState) {
  let state = initial, drafts: Drafts = {}, pending = false, error = '', active = true, generation = 0;
  const listeners = new Set<() => void>();
  function project(): { snapshot: PreferencesDraftSnapshot; patch: PreferencesPatch } {
    const text = {} as Record<PreferenceKey, string>, errors: Drafts = {}, patch: PreferencesPatch = {};
    for (const key of editablePreferenceKeys) {
      text[key] = drafts[key] ?? String(state.values[key]);
      if (!(key in drafts)) continue;
      const value = parse(key, text[key]);
      if (value === null) errors[key] = invalidMessage(key);
      else if (value !== state.values[key]) Object.assign(patch, { [key]: value });
    }
    return { snapshot: { drafts: { ...drafts }, text, errors, dirty: Object.keys(patch).length > 0 || Object.keys(errors).length > 0, pending, error }, patch };
  }
  let snapshot = project().snapshot;
  const publish = () => { snapshot = project().snapshot; if (active) listeners.forEach(listener => listener()); };
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    sync(next: PreferencesState) {
      if (!active || next.revision < state.revision) return;
      state = next;
      if (!project().snapshot.dirty) error = '';
      publish();
    },
    set(key: PreferenceKey, text: string) {
      if (!active || !editablePreferenceKeys.includes(key)) return;
      drafts = { ...drafts, [key]: text }; error = ''; publish();
    },
    resetDefaults() {
      if (!active || pending) return;
      drafts = Object.fromEntries(editablePreferenceKeys.map(key => [key, String(state.defaults[key])])); error = ''; publish();
    },
    /** Effect cleanup invalidates pending work, including React strict effect replay. */
    setActive(value: boolean) {
      if (active === value) return;
      generation++; active = value; pending = false; publish();
    },
    async apply(submit: (patch: PreferencesPatch) => Promise<void>): Promise<boolean> {
      if (!active || pending) return false;
      const next = project();
      if (Object.keys(next.snapshot.errors).length) { error = '请先修正设置输入。'; publish(); return false; }
      if (!Object.keys(next.patch).length) return true;
      const submitted = { ...drafts }, owner = generation;
      pending = true; error = ''; publish();
      try {
        await submit(next.patch);
        if (!active || owner !== generation) return false;
        drafts = { ...drafts };
        for (const key of editablePreferenceKeys) if (drafts[key] === submitted[key]) delete drafts[key];
        return true;
      } catch (cause) {
        if (active && owner === generation) error = cause instanceof Error ? cause.message : '设置未能保存，请重试。';
        return false;
      } finally {
        if (active && owner === generation) { pending = false; publish(); }
      }
    },
  };
}
