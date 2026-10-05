import { useEffect, useId, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import type { DocumentSnapshot } from '../workspace/types';
import type { FormDrafts, FormErrors, FormField, FormGroup } from './types';
import { ActionMenu } from './ActionMenu';
import { fieldHint, fieldText, shouldCommitKey } from './presentation';
import styles from './BasicForm.module.css';

export interface BasicFormProps {
  document: DocumentSnapshot;
  drafts: FormDrafts;
  errors: FormErrors;
  disabled: boolean;
  onDraft: (field: string, text: string) => void;
  onCommit: (field: string) => Promise<void>;
  onReset: (field: string) => void;
  onComposition: (field: string, composing: boolean) => void;
  onAction: (action: string, payload: Record<string, unknown>) => Promise<void>;
}

function Chevron({ expanded }: { expanded: boolean }) {
  return <svg viewBox="0 0 16 16" aria-hidden="true" className={styles.chevron} data-expanded={expanded}><path d="m6 4 4 4-4 4" /></svg>;
}

function Checkbox({ checked, label, disabled, onChange, invalid = false }: {
  checked: boolean | null; label: string; disabled: boolean; invalid?: boolean; onChange: (checked: boolean) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { if (ref.current) ref.current.indeterminate = checked === null; }, [checked]);
  return <span className={styles.checkbox} data-field-type="bool" data-disabled={disabled}>
    <input ref={ref} type="checkbox" checked={checked === true} aria-label={label} aria-invalid={invalid}
      disabled={disabled} onChange={event => onChange(event.target.checked)} />
    <span className={styles.checkboxFace} aria-hidden="true"><svg viewBox="0 0 14 14">{checked === null ? <path d="M3 7h8" /> : checked ? <path d="m3 7 2.5 2.5L11 4" /> : null}</svg></span>
  </span>;
}

function FieldControl({ field, drafts, error, disabled, onDraft, onCommit, onReset, onComposition, onAction }: {
  field: FormField; drafts: FormDrafts; error: string;
} & Pick<BasicFormProps, 'disabled' | 'onDraft' | 'onCommit' | 'onReset' | 'onComposition' | 'onAction'>) {
  const composing = useRef(false);
  const compositionCallback = useRef(onComposition);
  compositionCallback.current = onComposition;
  const id = useId();
  const inactive = Boolean(field.inactiveReason);
  const locked = disabled || field.readOnly || inactive;
  const multiline = field.control === 'string' && field.name === 'description';
  const commit = () => { if (!composing.current && !locked) void onCommit(field.name).catch(() => {}); };
  const action = (value: unknown) => { void onAction('set_field', { field: field.name, value }).catch(() => {}); };
  useEffect(() => () => { if (composing.current) compositionCallback.current(field.name, false); }, [field.name]);
  const keyDown = (event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const activeComposition = composing.current || event.nativeEvent.isComposing;
    if (shouldCommitKey(event.key, activeComposition, multiline, event.ctrlKey || event.metaKey, event.nativeEvent.keyCode)) {
      event.preventDefault(); commit();
    } else if (event.key === 'Escape' && !activeComposition) {
      event.preventDefault(); event.stopPropagation(); onReset(field.name);
    }
  };
  const inputProps = {
    id, 'aria-label': field.label, 'aria-invalid': Boolean(error), 'aria-describedby': error ? `${id}-error` : inactive ? `${id}-inactive` : undefined,
    title: fieldHint(field), disabled: locked, value: fieldText(field, drafts),
    placeholder: field.present && field.value === null ? '空值' : undefined,
    onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onDraft(field.name, event.target.value),
    onBlur: commit, onKeyDown: keyDown,
    onCompositionStart: () => { composing.current = true; onComposition(field.name, true); },
    onCompositionEnd: () => { composing.current = false; onComposition(field.name, false); },
  };
  const isReadonly = field.control === 'readonly' || field.readOnly;
  return <div className={styles.field} data-field={field.name} data-field-type={field.fieldType} data-inactive={inactive}>
    <label className={styles.label} htmlFor={isReadonly || field.control === 'boolean' ? undefined : id} title={fieldHint(field)}>{field.label}</label>
    <div className={styles.valueColumn}>
      <div className={styles.control} data-control={field.control} data-field-type={field.fieldType} title={fieldHint(field)}>
        {isReadonly ? <output className={styles.readonly} aria-label={field.label} aria-invalid={Boolean(error)}>{field.displayValue === null ? '空值' : typeof field.displayValue === 'object' ? JSON.stringify(field.displayValue, null, 2) : String(field.displayValue ?? '')}</output>
          : field.control === 'boolean' ? <div className={styles.booleanControl}><Checkbox checked={field.present && field.value === null ? null : Boolean(field.displayValue)}
            label={field.label} disabled={locked} invalid={Boolean(error)} onChange={action} /></div>
            : multiline ? <textarea {...inputProps} rows={3} />
              : <input {...inputProps} type="text" inputMode={field.control === 'number' ? field.integer ? 'numeric' : 'decimal' : 'text'} />}
        {!isReadonly && field.control === 'color' && <input className={styles.colorPicker} type="color" aria-label={`选择${field.label}`}
          title={`选择${field.label}，保留透明度`} disabled={locked} value={field.swatchHex ?? '#000000'} onChange={event => action(event.target.value)} />}
      </div>
      {error && <p className={styles.error} id={`${id}-error`} role="alert">{error}</p>}
      {inactive && <p className={styles.inactive} id={`${id}-inactive`}>{field.inactiveReason}</p>}
    </div>
    <div className={styles.fieldActions}>
      {((!field.readOnly && field.nullable) || field.deletable) && <ActionMenu label={`${field.label}的操作`} disabled={disabled}
        items={[
          ...(!field.readOnly && field.nullable && !inactive ? [{ id: 'null', label: '设置为空值', run: () => action(null) }] : []),
          ...(field.deletable ? [{ id: 'delete', label: '删除字段', run: () => { void onAction('delete_field', { field: field.name }).catch(() => {}); } }] : []),
        ]}><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="3" cy="8" r=".8" /><circle cx="8" cy="8" r=".8" /><circle cx="13" cy="8" r=".8" /></svg></ActionMenu>}
    </div>
  </div>;
}

export function BasicForm(props: BasicFormProps) {
  const { document: doc, drafts, errors, disabled, onAction } = props;
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const prefix = useId();
  useEffect(() => setExpanded({}), [doc.path, doc.sessionId]);
  const toggle = (group: FormGroup) => setExpanded(current => ({ ...current, [group.id]: !(current[group.id] ?? group.defaultExpanded) }));
  const run = (action: string, payload: Record<string, unknown>) => { void onAction(action, payload).catch(() => {}); };
  return <div className={styles.form} aria-label="内容字段">
    {doc.form.groups.map(group => {
      const open = (expanded[group.id] ?? group.defaultExpanded) && (!group.capability || group.enabled);
      const bodyId = `${prefix}-${group.id}`;
      return <section className={styles.group} key={group.id} data-group={group.id} data-enabled={!group.capability || group.enabled}>
        <div className={styles.groupHead}>
          <button className={styles.fold} type="button" aria-label={`${open ? '折叠' : '展开'}${group.label}`} aria-expanded={open} aria-controls={bodyId}
            disabled={group.capability && !group.enabled} onClick={() => toggle(group)}><Chevron expanded={open} /></button>
          {group.capability && <Checkbox label={`启用${group.label}`} checked={group.enabled} disabled={disabled} onChange={enabled => {
            void onAction('set_capability', { group: group.id, enabled }).then(() => {
              if (enabled) setExpanded(current => group.id in current ? current : { ...current, [group.id]: true });
            }).catch(() => {});
          }} />}
          <button className={styles.groupTitle} type="button" aria-expanded={open} aria-controls={bodyId}
            disabled={group.capability && !group.enabled} onClick={() => toggle(group)}>{group.label}</button>
          {group.locked && <span className={styles.lock} title="锁定字段组，不能删除" aria-label="锁定字段组"><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5 7V5a3 3 0 0 1 6 0v2M4 7h8v7H4Z" /></svg></span>}
          <ActionMenu label={`添加${group.label}字段`} disabled={disabled || (group.capability && !group.enabled)}
            items={group.addableFields.map(field => ({ id: field.name, label: field.label, run: () => {
              void onAction('add_field', { group: group.id, field: field.name }).then(() => setExpanded(current => ({ ...current, [group.id]: true }))).catch(() => {});
            } }))}><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3v10M3 8h10" /></svg></ActionMenu>
          {!group.locked && <button type="button" className={styles.iconButton} disabled={disabled} aria-label={`删除${group.label}组`} title={`删除${group.label}组`}
            onClick={() => run('delete_group', { group: group.id })}><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m5 5 6 6M11 5l-6 6" /></svg></button>}
        </div>
        {open && <div id={bodyId} className={styles.groupBody}>{group.fields.length ? group.fields.map(field => <FieldControl key={field.name} {...props}
          field={field} error={errors[field.name] ?? field.validationError} />) : <p className={styles.empty}>此组暂无字段，可从右上方添加。</p>}</div>}
      </section>;
    })}
    <div className={styles.formFoot}><ActionMenu label="添加字段组" disabled={disabled} items={doc.form.addableGroups.map(group => ({ id: group.id, label: group.label,
      run: () => { void onAction('add_group', { group: group.id }).then(() => setExpanded(current => ({ ...current, [group.id]: true }))).catch(() => {}); } }))}>
      添加字段组
    </ActionMenu></div>
  </div>;
}
