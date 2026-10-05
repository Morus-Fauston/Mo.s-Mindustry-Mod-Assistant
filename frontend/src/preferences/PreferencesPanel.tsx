import { useEffect, useId, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { FormEvent } from 'react';
import { createPreferencesDrafts } from './drafts';
import type { PreferenceKey, PreferencesPatch, PreferencesState } from './types';
import styles from './PreferencesPanel.module.css';

export interface PreferencesPanelProps {
  state: PreferencesState;
  busy: boolean;
  error: string;
  /** Resolve only after accepting the saved authoritative preferences; reject failures. */
  onUpdate: (patch: PreferencesPatch) => Promise<void>;
  onClose: () => void;
  recovery?: { busy: boolean; onRecover(): Promise<void> };
}
const fields: { key: PreferenceKey; label: string; type: 'str' | 'num'; hint: string;
  choices?: { value: string; label: string }[] }[] = [
  { key: 'theme', label: '主题', type: 'str', hint: '选择工作台的浅色或深色外观。',
    choices: [{ value: 'light', label: '浅色' }, { value: 'dark', label: '深色' }] },
  { key: 'display_name_mode', label: '字段显示名', type: 'str', hint: '只调整字段名称的显示方式。', choices: [
    { value: 'zh_en', label: '中文（英文）' }, { value: 'en_zh', label: '英文（中文）' },
    { value: 'zh', label: '纯中文' }, { value: 'en', label: '纯英文' }] },
  { key: 'auto_save_interval', label: '自动保存间隔', type: 'num', hint: '单位为秒，范围 0 至 3600；0 表示关闭。自动保存会写入内容文件。' },
  { key: 'sprite_zoom', label: '预览倍率', type: 'num', hint: '范围 1 至 8，只调整贴图的预览大小。' },
];

/** Controlled authoritative settings with an instance-local, non-persistent input buffer. */
export function PreferencesPanel(props: PreferencesPanelProps) {
  const [drafts] = useState(() => createPreferencesDrafts(props.state));
  const input = useSyncExternalStore(drafts.subscribe, drafts.getSnapshot, drafts.getSnapshot);
  const id = useId(), dialog = useRef<HTMLDialogElement>(null), composing = useRef(false);
  const latest = useRef(props); latest.current = props;
  const locked = props.busy || input.pending;
  useEffect(() => {
    drafts.setActive(true);
    return () => { drafts.setActive(false); };
  }, [drafts]);
  useEffect(() => { drafts.sync(props.state); }, [drafts, props.state]);
  useLayoutEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const element = dialog.current;
    element?.showModal();
    return () => {
      element?.close();
      queueMicrotask(() => {
        if (previous?.isConnected && !previous.matches(':disabled') && !document.querySelector('dialog[open]')) previous.focus({ preventScroll: true });
      });
    };
  }, []);
  const close = () => { if (!latest.current.busy && !drafts.getSnapshot().pending) latest.current.onClose(); };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (latest.current.busy || composing.current || drafts.getSnapshot().pending) return;
    void drafts.apply(patch => latest.current.onUpdate(patch));
  };
  const failure = input.error || props.error;
  return <dialog ref={dialog} className={styles.dialog} aria-labelledby={`${id}-title`}
    onCancel={event => { event.preventDefault(); close(); }}>
    <form noValidate onSubmit={submit} aria-busy={locked}
      onCompositionStart={() => { composing.current = true; }} onCompositionEnd={() => { composing.current = false; }}>
      <h2 id={`${id}-title`}>设置</h2>
      <p className={styles.intro}>修改后点击应用，关闭窗口可放弃尚未应用的输入。</p>
      {props.state.warnings.map((warning, index) => <p className={styles.warning} role="status" key={index}>{warning}</p>)}
      {fields.map(field => {
        const error = input.errors[field.key], fieldId = `${id}-${field.key}`;
        const common = { id: fieldId, 'aria-label': field.label, disabled: locked, value: input.text[field.key],
          'aria-invalid': Boolean(error), 'aria-describedby': `${fieldId}-hint${error ? ` ${fieldId}-error` : ''}` };
        return <div className={styles.field} data-preference={field.key} key={field.key}>
          <label htmlFor={fieldId}>{field.label}</label>
          <div className={styles.value}>
            <div className={styles.control} data-field-type={field.type}>
              {field.choices ? <select {...common} data-field-type={field.type} onChange={event => drafts.set(field.key, event.target.value)}>
                {field.choices.map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
              </select> : <input {...common} type="text" inputMode="numeric" data-field-type={field.type}
                autoComplete="off" spellCheck={false} onChange={event => drafts.set(field.key, event.target.value)} />}
            </div>
            <p className={styles.hint} id={`${fieldId}-hint`}>{field.hint}</p>
            {error && <p className={styles.error} id={`${fieldId}-error`}>{error}</p>}
          </div>
        </div>;
      })}
      {failure && <p className={styles.error} role="alert">{failure}</p>}
      {props.recovery && <button type="button" disabled={props.recovery.busy}
        onClick={() => void props.recovery?.onRecover().catch(() => {})}>查询配置结果</button>}
      <footer className={styles.actions}>
        <button type="button" className={styles.defaults} disabled={locked} onClick={() => drafts.resetDefaults()}>恢复默认</button>
        <button type="button" disabled={locked} onClick={close}>关闭</button>
        <button type="submit" disabled={locked || !input.dirty}>{locked ? '正在应用' : '应用'}</button>
      </footer>
    </form>
  </dialog>;
}
