import { useEffect, useId, useRef, useState } from 'react';
import { BasicForm, type BasicFormProps } from '../forms/BasicForm';
import type { FormField } from '../forms/types';
import { encodeFieldKey, moveBefore, scopedFields } from './address';
import type { NestedArrayField, NestedArrayItem, NestedField, NestedFormPlan, NestedObjectField, ObjectPath } from './types';
import styles from './NestedForm.module.css';

export { decodeFieldKey, encodeFieldKey, findNestedField } from './address';
export type { NestedFormPlan, ObjectPath } from './types';

export interface NestedFormProps extends Omit<BasicFormProps, 'renderField'> {
  plan: NestedFormPlan;
}

interface NodeProps { root: NestedFormProps; plan: NestedFormPlan }

function shellField(field: NestedField): FormField {
  return field.control === 'object' || field.control === 'array'
    ? { ...field, control: 'readonly', readOnly: true } : field;
}

/** A single input-buffer namespace; Python remains the only data/history owner. */
export function NestedForm(props: NestedFormProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  const owner = `${props.document.sessionId}/${props.document.path}`;
  const ownerRef = useRef(owner);
  ownerRef.current = owner;
  useEffect(() => { busy.current = false; setPending(false); setError(''); }, [owner]);
  const action: BasicFormProps['onAction'] = async (name, payload) => {
    if (props.disabled || busy.current) throw new Error('正在提交修改，请稍后重试。');
    busy.current = true; setPending(true); setError('');
    try { await props.onAction(name, payload); }
    catch (failure) {
      if (ownerRef.current === owner) setError(failure instanceof Error ? failure.message : '修改未能完成，请重试。');
      throw failure;
    } finally {
      if (ownerRef.current === owner) { busy.current = false; setPending(false); }
    }
  };
  return <div className={styles.nested} aria-label="嵌套内容字段" aria-busy={pending}>
    {error && <p className={styles.error} role="alert">{error}</p>}
    <NodeForm key={owner} root={{ ...props, disabled: props.disabled || pending, onAction: action }} plan={props.plan} />
  </div>;
}

function NodeForm({ root, plan }: NodeProps) {
  const id = useId();
  const allFields = plan.groups.flatMap(group => group.fields);
  const fieldKey = (name: string) => encodeFieldKey(plan.objectPath, name);
  const run = (action: string, payload: Record<string, unknown>) => root.onAction(action, { ...payload, objectPath: plan.objectPath });
  const type = plan.typeSelector;
  const selectedKnown = type?.choices.some(choice => choice.value === type.value);
  return <div className={styles.node} data-object-path={JSON.stringify(plan.objectPath)}>
    {type && <div className={styles.typeRow}>
      <label htmlFor={id}>{root.document.fieldNames.type ?? '类型'}</label>
      <select id={id} aria-label={root.document.fieldNames.type ?? '类型'} value={type.value ?? ''} disabled={root.disabled}
        title={root.document.fieldDocs.type ?? ''} onChange={event => void run('set_type', { type: event.target.value }).catch(() => {})}>
        {!selectedKnown && <option value={type.value ?? ''} disabled>{type.value ? `${plan.knownType ? '当前基础类型' : '未识别类型'}：${type.value}` : '未写入类型，当前使用默认显示'}</option>}
        {type.choices.map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
      </select>
    </div>}
    {plan.notice && <p className={styles.notice} role="status">{plan.notice}</p>}
    <BasicForm document={{ ...root.document, form: { ...plan, groups: plan.groups.map(group => ({ ...group, fields: group.fields.map(shellField) })) } }}
      drafts={scopedFields(root.drafts, plan.objectPath, allFields)} errors={scopedFields(root.errors, plan.objectPath, allFields)} disabled={root.disabled}
      onDraft={(field, text) => root.onDraft(fieldKey(field), text)} onCommit={field => root.onCommit(fieldKey(field))}
      onReset={field => root.onReset(fieldKey(field))} onComposition={(field, composing) => root.onComposition(fieldKey(field), composing)}
      onAction={run} onLoadReference={(field, query) => root.onLoadReference(fieldKey(field), query)}
      renderField={field => {
        const nested = allFields.find(candidate => candidate.name === field.name);
        if (nested?.control === 'object') return <ObjectControl root={root} plan={plan} field={nested} />;
        if (nested?.control === 'array') return <ArrayControl root={root} plan={plan} field={nested} />;
        return undefined;
      }} />
  </div>;
}

function FoldIcon({ expanded }: { expanded: boolean }) {
  return <svg viewBox="0 0 16 16" aria-hidden="true" data-expanded={expanded}><path d="m6 4 4 4-4 4" /></svg>;
}

function ObjectControl({ root, plan, field }: NodeProps & { field: NestedObjectField }) {
  const [expanded, setExpanded] = useState(true);
  const id = useId();
  const locked = root.disabled || field.readOnly || Boolean(field.inactiveReason);
  const error = root.errors[encodeFieldKey(plan.objectPath, field.name)] ?? field.validationError;
  const run = (action: string) => void root.onAction(action, { objectPath: plan.objectPath, field: field.name }).catch(() => {});
  return <section className={styles.container} data-field={field.name} data-field-type="obj" aria-label={field.label} aria-invalid={Boolean(error)}>
    <header className={styles.heading}>
      <button type="button" className={styles.title} aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded(value => !value)} title={field.help}>
        <FoldIcon expanded={expanded} />{field.label}
      </button>
      {field.deletable && <button type="button" disabled={root.disabled} aria-label={`删除${field.label}字段`} onClick={() => run('delete_field')}>删除字段</button>}
    </header>
    {expanded && <div id={id} className={styles.body}>
      {field.child ? <NodeForm root={{ ...root, disabled: locked }} plan={field.child} />
        : field.canCreate ? <button type="button" disabled={locked} onClick={() => run('create_object')}>创建{field.label}</button>
          : <output className={styles.notice}>{typeof field.displayValue === 'object' ? JSON.stringify(field.displayValue) : String(field.displayValue ?? '空值')}</output>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {field.inactiveReason && <p className={styles.notice}>{field.inactiveReason}</p>}
    </div>}
  </section>;
}

function ArrayControl({ root, plan, field }: NodeProps & { field: NestedArrayField }) {
  const [expanded, setExpanded] = useState(true);
  const [closedItems, setClosedItems] = useState<Record<string, boolean>>({});
  const id = useId();
  const listRef = useRef<HTMLDivElement>(null);
  const addRef = useRef<HTMLButtonElement>(null);
  const restoreFocus = useRef<string | null | undefined>(undefined);
  const locked = root.disabled || field.readOnly || Boolean(field.inactiveReason);
  const error = root.errors[encodeFieldKey(plan.objectPath, field.name)] ?? field.validationError;
  const run = (action: string, payload: Record<string, unknown> = {}) => root.onAction(action, { ...payload, objectPath: plan.objectPath, field: field.name });

  useEffect(() => {
    if (root.disabled || restoreFocus.current === undefined) return;
    const target = restoreFocus.current;
    restoreFocus.current = undefined;
    const button = target ? listRef.current?.querySelector<HTMLButtonElement>(`[data-item-id="${target}"] [data-item-title]`) : addRef.current;
    button?.focus({ preventScroll: true });
  }, [root.disabled, field.items]);

  async function remove(itemId: string) {
    const index = field.items.findIndex(item => item.itemId === itemId);
    const next = field.items[index + 1]?.itemId ?? field.items[index - 1]?.itemId ?? null;
    restoreFocus.current = next;
    try { await run('array_remove', { itemId }); }
    catch { restoreFocus.current = undefined; }
  }

  function move(itemId: string, direction: 'up' | 'down') {
    const beforeItemId = moveBefore(field.items, itemId, direction);
    if (beforeItemId !== undefined) {
      restoreFocus.current = itemId;
      void run('array_move', { itemId, beforeItemId }).catch(() => { restoreFocus.current = undefined; });
    }
  }

  const scalarPlan = (item: NestedArrayItem, objectPath: ObjectPath): NestedFormPlan => ({
    objectPath, contentType: item.field?.javaType ?? '', knownType: true,
    groups: [{ id: 'value', label: field.label, locked: true, defaultExpanded: true, capability: false, enabled: true,
      fields: item.field ? [{ ...item.field, deletable: false }] : [], addableFields: [] }], addableGroups: [],
  });

  return <section className={styles.container} data-field={field.name} data-field-type="arr" aria-label={field.label} aria-invalid={Boolean(error)}>
    <header className={styles.heading}>
      <button type="button" className={styles.title} aria-expanded={expanded} aria-controls={id} onClick={() => setExpanded(value => !value)} title={field.help}>
        <FoldIcon expanded={expanded} />{field.label}<span className={styles.count}>{field.items.length} 项</span>
      </button>
      {field.deletable && <button type="button" disabled={root.disabled} aria-label={`删除${field.label}字段`} onClick={() => void run('delete_field').catch(() => {})}>删除字段</button>}
    </header>
    {expanded && <div id={id} className={styles.body} ref={listRef}>
      {!field.items.length && <p className={styles.notice}>当前没有项目。</p>}
      {field.items.map((item, index) => {
        const open = !closedItems[item.itemId];
        const bodyId = `${id}-${item.itemId}`;
        const itemPath: ObjectPath = [...plan.objectPath, field.name, { itemId: item.itemId }];
        return <section className={styles.item} key={item.itemId} data-item-id={item.itemId}>
          <header className={styles.itemHead}>
            <button type="button" className={styles.title} data-item-title aria-expanded={open} aria-controls={bodyId}
              onClick={() => setClosedItems(current => ({ ...current, [item.itemId]: open }))}>
              <FoldIcon expanded={open} />第 {index + 1} 项
            </button>
            <div className={styles.actions}>
              <button type="button" disabled={locked || !field.canMove || index === 0} aria-label={`上移第 ${index + 1} 项`} onClick={() => move(item.itemId, 'up')}>上移</button>
              <button type="button" disabled={locked || !field.canMove || index === field.items.length - 1} aria-label={`下移第 ${index + 1} 项`} onClick={() => move(item.itemId, 'down')}>下移</button>
              <button type="button" disabled={locked || !field.canRemove} aria-label={`删除第 ${index + 1} 项`} onClick={() => void remove(item.itemId)}>删除</button>
            </div>
          </header>
          {open && <div id={bodyId} className={styles.itemBody}>
            {item.form ? <NodeForm root={{ ...root, disabled: locked }} plan={item.form} />
              : item.field ? <NodeForm root={{ ...root, disabled: locked }} plan={scalarPlan(item, itemPath)} />
                : <p className={styles.notice}>{item.notice ?? '此项目暂不支持表单编辑，原值已保留。'}</p>}
          </div>}
        </section>;
      })}
      <button ref={addRef} type="button" className={styles.add} disabled={locked || !field.canInsert} onClick={() => void run('array_insert').catch(() => {})}>添加{field.label}项</button>
      {error && <p className={styles.error} role="alert">{error}</p>}
      {field.inactiveReason && <p className={styles.notice}>{field.inactiveReason}</p>}
    </div>}
  </section>;
}
