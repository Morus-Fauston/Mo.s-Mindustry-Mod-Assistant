import { useEffect, useId, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { FormEvent, RefObject } from 'react';
import { createContentToolsState } from './state';
import type { ContentDialog, ContentForm, ContentToolsProps, ContentToolsSnapshot } from './types';
import styles from './ContentTools.module.css';

export type { ContentAction, ContentCatalogue, ContentToolsProps } from './types';

const titles: Record<ContentDialog, string> = {
  create_project: '新建工程', create_content: '新建内容', rename_content: '重命名内容', delete_content: '删除内容',
};

export function ContentTools(props: ContentToolsProps) {
  const latest = useRef(props);
  const opener = useRef<HTMLButtonElement>(null);
  latest.current = props;
  const [state] = useState(() => createContentToolsState({
    loadCatalogue: () => latest.current.loadCatalogue(),
    onAction: (action, payload) => latest.current.onAction(action, payload),
  }));
  const snapshot = useSyncExternalStore(state.subscribe, state.getSnapshot, state.getSnapshot);
  useLayoutEffect(() => state.session(props.sessionId), [props.sessionId, state]);
  useEffect(() => { if (props.completionId) state.complete(); }, [props.completionId, state]);
  useEffect(() => () => state.dispose(), [state]);
  const blocked = props.disabled || snapshot.submitting || snapshot.mode !== null;
  const open = (mode: ContentDialog, button: HTMLButtonElement) => {
    if (!blocked) { opener.current = button; void state.open(mode, props.activePath); }
  };
  return <div className={styles.tools} aria-label="工程与内容操作">
    <button type="button" className={styles.button} disabled={blocked} onClick={event => open('create_project', event.currentTarget)}>新建工程</button>
    <button type="button" className={styles.button} disabled={blocked || !props.sessionId} onClick={event => open('create_content', event.currentTarget)}>新建内容</button>
    <button type="button" className={styles.button} disabled={blocked || !props.sessionId || !props.activePath}
      onClick={event => open('rename_content', event.currentTarget)}>重命名</button>
    <button type="button" className={styles.button} disabled={blocked || !props.sessionId || !props.activePath}
      onClick={event => open('delete_content', event.currentTarget)}>删除内容</button>
    <button type="button" className={styles.button} disabled={blocked || !props.sessionId || !props.activePath}
      onClick={() => { if (!blocked) void state.reveal(props.activePath); }}>定位文件</button>
    {!snapshot.mode && snapshot.error && <span className={styles.error} role="alert">{snapshot.error}</span>}
    {snapshot.mode && <ContentActionDialog key={`${props.sessionId}:${snapshot.mode}`} snapshot={snapshot}
      disabled={props.disabled} returnFocus={opener} onUpdate={state.update} onCancel={state.cancel} onReload={() => void state.reload()}
      recovery={props.recovery} recoveryBusy={props.recoveryBusy} onRecover={props.onRecover}
      onSubmit={overwrite => { if (!props.disabled) void state.submit(overwrite); }} />}
  </div>;
}

interface DialogProps {
  snapshot: ContentToolsSnapshot;
  disabled: boolean;
  returnFocus: RefObject<HTMLButtonElement | null>;
  onUpdate: (field: keyof ContentForm, value: string) => void;
  onCancel: () => void;
  onReload: () => void;
  onSubmit: (overwrite?: boolean) => void;
  recovery?: boolean;
  recoveryBusy?: boolean;
  onRecover?: () => Promise<void>;
}

function TextField({ id, label, value, disabled, required = false, pattern, describedBy, inputRef, onChange }: {
  id: string; label: string; value: string; disabled: boolean; required?: boolean; pattern?: string;
  describedBy?: string; inputRef?: RefObject<HTMLInputElement | null>; onChange: (value: string) => void;
}) {
  return <div className={styles.field}>
    <label htmlFor={id}>{label}</label>
    <input ref={inputRef} id={id} value={value} disabled={disabled} required={required} pattern={pattern}
      data-field-type="str" aria-describedby={describedBy} autoComplete="off" spellCheck={false}
      onChange={event => onChange(event.target.value)} />
  </div>;
}

function ContentActionDialog({ snapshot, disabled, returnFocus, onUpdate, onCancel, onReload, onSubmit, recovery, recoveryBusy, onRecover }: DialogProps) {
  const [recoveryError, setRecoveryError] = useState('');
  const id = useId(), dialog = useRef<HTMLDialogElement>(null), initialInput = useRef<HTMLInputElement>(null);
  const cancel = useRef<HTMLButtonElement>(null), focused = useRef(false);
  const latest = useRef({ onCancel, submitting: snapshot.submitting });
  latest.current = { onCancel, submitting: snapshot.submitting };
  const mode = snapshot.mode!;
  const { form, catalogue, loading, submitting, conflict, error } = snapshot;
  const locked = disabled || submitting || loading;
  const nameHint = `${id}-name-hint`;
  useLayoutEffect(() => {
    const previous = returnFocus.current ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    const element = dialog.current;
    element?.showModal();
    return () => {
      element?.close();
      // The opener is disabled while the dialog is mounted. Restore only after
      // React has applied the sibling toolbar's enabled state for this commit.
      queueMicrotask(() => {
        if (previous?.isConnected && !previous.matches(':disabled') && !document.querySelector('dialog[open]')) {
          previous.focus({ preventScroll: true });
        }
      });
    };
  }, []);
  useEffect(() => {
    if (!loading && !disabled && !focused.current) {
      if (mode === 'delete_content') cancel.current?.focus();
      else { initialInput.current?.focus(); if (mode === 'rename_content') initialInput.current?.select(); }
      focused.current = true;
    }
  }, [loading, disabled, mode]);
  const category = catalogue?.categories.find(item => item.id === form.category);
  // HTML patterns use the Unicode-v grammar: a literal final hyphen in a
  // character class needs escaping, unlike the Python source expression.
  const namePattern = catalogue?.namePattern.replace(/-\]/g, '\\-]');
  const grouped = new Map<string, { kind: string; label: string }[]>();
  for (const item of category?.templates ?? []) {
    const key = item.group ?? '';
    grouped.set(key, [...(grouped.get(key) ?? []), item]);
  }
  const needsCatalogue = mode !== 'delete_content';
  const canSubmit = !locked && (!needsCatalogue || catalogue !== null) &&
    (mode !== 'create_content' || Boolean(form.category && form.kind && form.name.trim())) &&
    (mode !== 'rename_content' || Boolean(form.name.trim())) &&
    (mode !== 'create_project' || Boolean(form.modId.trim()));
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (canSubmit && !conflict) onSubmit(false);
  };
  return <dialog ref={dialog} className={styles.dialog} aria-labelledby={`${id}-title`}
    onCancel={event => { event.preventDefault(); if (!latest.current.submitting) latest.current.onCancel(); }}>
    <form onSubmit={handleSubmit} aria-busy={submitting || loading}>
      <h2 id={`${id}-title`}>{titles[mode]}</h2>
      {(mode === 'rename_content' || mode === 'delete_content') && <p className={styles.path}>{snapshot.targetPath}</p>}
      {mode === 'delete_content' ? <p>确认删除这个内容文件？匹配贴图会保留，完成后可撤销。</p> : <>
        {mode === 'create_content' && <>
          <div className={styles.field}>
            <label htmlFor={`${id}-category`}>内容类别</label>
            <select id={`${id}-category`} data-field-type="ref" value={form.category} disabled={locked || !catalogue} onChange={event => onUpdate('category', event.target.value)}>
              {!form.category && <option value="">请选择内容类别</option>}
              {catalogue?.categories.map(item => <option key={item.id} value={item.id} disabled={!item.templates.length}>{item.label}</option>)}
            </select>
          </div>
          <div className={styles.field}>
            <label htmlFor={`${id}-template`}>内容模板</label>
            <select id={`${id}-template`} data-field-type="ref" value={form.kind} disabled={locked || !category?.templates.length} onChange={event => onUpdate('kind', event.target.value)}>
              {!form.kind && <option value="">没有可用模板</option>}
              {[...grouped].map(([group, items]) => group ? <optgroup key={group} label={group}>{items.map(item => <option key={item.kind} value={item.kind}>{item.label}</option>)}</optgroup>
                : items.map(item => <option key={item.kind} value={item.kind}>{item.label}</option>))}
            </select>
          </div>
        </>}
        {mode === 'create_project' ? <>
          <TextField id={`${id}-mod-id`} label="模组 ID" value={form.modId} disabled={locked} required pattern={namePattern}
            inputRef={initialInput} describedBy={nameHint} onChange={value => onUpdate('modId', value)} />
          <TextField id={`${id}-display-name`} label="显示名称" value={form.displayName} disabled={locked} onChange={value => onUpdate('displayName', value)} />
          <TextField id={`${id}-author`} label="作者" value={form.author} disabled={locked} onChange={value => onUpdate('author', value)} />
          <p className={styles.hint}>下一步选择父目录，然后在其中创建以模组 ID 命名的工程文件夹。</p>
        </> : <TextField id={`${id}-name`} label={mode === 'rename_content' ? '新名称' : '内容名称'} value={form.name}
          disabled={locked} required pattern={namePattern} inputRef={initialInput} describedBy={nameHint} onChange={value => onUpdate('name', value)} />}
        <p id={nameHint} className={styles.hint}>{catalogue?.nameHint ?? (loading ? '正在读取名称规则与模板…' : '名称规则尚未就绪。')}</p>
        {mode === 'rename_content' && <p className={styles.hint}>匹配贴图与已有的名称字段会同步修改，其他内容中的引用保持原样。</p>}
        {mode === 'create_content' && catalogue && !category?.templates.length && <p className={styles.hint}>当前没有可用模板，请检查离线资料后重试。</p>}
      </>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {recovery && onRecover && <button className={styles.button} type="button" disabled={recoveryBusy}
        onClick={() => { setRecoveryError(''); void onRecover().catch(error => setRecoveryError(error instanceof Error ? error.message : '查询失败，请重试。')); }}>查询原操作结果</button>}
      {recoveryError && <p className={styles.error} role="alert">{recoveryError}</p>}
      {needsCatalogue && !catalogue && !loading && <button className={styles.button} type="button" disabled={submitting} onClick={onReload}>重试读取选项</button>}
      {conflict && <div className={styles.confirmation}>
        <p>所选类别中已存在同名文件。覆盖会替换该文件内容；继续前会处理未保存的修改。</p>
        <button className={`${styles.button} ${styles.destructive}`} type="button" disabled={!canSubmit}
          onClick={() => { if (dialog.current?.querySelector('form')?.reportValidity()) onSubmit(true); }}>确认覆盖此文件</button>
      </div>}
      <div className={styles.actions}>
        <button ref={cancel} className={styles.button} type="button" disabled={submitting} onClick={onCancel}>取消</button>
        {!conflict && <button className={`${styles.button} ${mode === 'delete_content' ? styles.destructive : ''}`} type="submit" disabled={!canSubmit}>
          {submitting ? (mode === 'create_project' ? '请选择工程目录…' : '正在处理…') : mode === 'delete_content' ? '确认删除内容'
            : mode === 'rename_content' ? '确认重命名' : mode === 'create_project' ? '选择父目录并创建' : '创建内容'}
        </button>}
      </div>
    </form>
  </dialog>;
}
