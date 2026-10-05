import { useEffect, useId, useRef, useState } from 'react';
import { BasicForm, type BasicFormProps } from '../forms/BasicForm';
import { ActionMenu } from '../forms/ActionMenu';
import type { FormField } from '../forms/types';
import { encodeFieldKey, moveBefore } from '../nested/address';
import type { ObjectPath } from '../nested/types';
import { resourceLeafProps } from './address';
import { isResourceField, type ResourceDescriptor, type ResourceListField } from './types';
import styles from './ResourceField.module.css';

export { findResourceField } from './address';
export { isResourceField } from './types';
export type { ResourceDescriptor } from './types';

export interface ResourceFieldProps extends Omit<BasicFormProps, 'renderField'> {
  field: ResourceDescriptor;
  objectPath: ObjectPath;
}

export function ResourceField(props: ResourceFieldProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const busy = useRef(false);
  const generation = useRef(0);
  const owner = `${props.document.sessionId}/${props.document.path}`;
  const ownerRef = useRef(owner);
  ownerRef.current = owner;
  useEffect(() => {
    generation.current += 1; busy.current = false; setPending(false); setError('');
    return () => { generation.current += 1; };
  }, [owner]);
  const action: BasicFormProps['onAction'] = async (name, payload) => {
    if (props.disabled || busy.current) throw new Error('正在提交修改，请稍后重试。');
    const requestGeneration = generation.current;
    busy.current = true; setPending(true); setError('');
    try { await props.onAction(name, payload); }
    catch (failure) {
      if (ownerRef.current === owner && generation.current === requestGeneration) setError(failure instanceof Error ? failure.message : '资源修改未能完成，请重试。');
      throw failure;
    } finally {
      if (ownerRef.current === owner && generation.current === requestGeneration) { busy.current = false; setPending(false); }
    }
  };
  return <div aria-busy={pending} className={styles.resource}>
    {error && <p className={styles.error} role="alert">{error}</p>}
    <ResourceControl key={owner} {...props} disabled={props.disabled || pending} onAction={action} />
  </div>;
}

function Fold({ expanded }: { expanded: boolean }) {
  return <svg viewBox="0 0 16 16" aria-hidden="true" data-expanded={expanded}><path d="m6 4 4 4-4 4" /></svg>;
}

function Leaves({ root, objectPath, fields }: { root: ResourceFieldProps; objectPath: ObjectPath; fields: FormField[] }) {
  return <div className={styles.leaves}><BasicForm {...resourceLeafProps(root, objectPath, fields)} /></div>;
}

function ResourceControl(props: ResourceFieldProps) {
  const { field, objectPath } = props;
  const [expanded, setExpanded] = useState(true);
  const id = useId();
  const error = props.errors[encodeFieldKey(objectPath, field.name)] ?? field.validationError;
  const locked = props.disabled || field.readOnly || Boolean(field.inactiveReason);
  const root = { ...props, disabled: locked };
  const run = (action: string, extra: Record<string, unknown> = {}) => props.onAction(action, { ...extra, objectPath, field: field.name });
  return <section className={styles.container} data-field={field.name} data-field-type={field.control === 'resource_list' ? 'arr' : field.control === 'consumes' ? 'obj' : 'ref'}
    aria-label={field.label} aria-invalid={Boolean(error)}>
    <header className={styles.heading}>
      <button type="button" className={styles.title} aria-expanded={expanded} aria-controls={id} title={field.help}
        onClick={() => setExpanded(value => !value)}><Fold expanded={expanded} />{field.label}
        {field.control === 'resource_list' && <span className={styles.count}>{field.rows.length} 项</span>}
      </button>
      {field.deletable && <button type="button" disabled={props.disabled} aria-label={`删除${field.label}字段`}
        onClick={() => void run('delete_field').catch(() => {})}>删除字段</button>}
    </header>
    {expanded && <div id={id} className={styles.body}>
      {field.readOnly ? <output className={styles.notice}>{field.displayValue === null ? '空值' : typeof field.displayValue === 'object' ? JSON.stringify(field.displayValue) : String(field.displayValue ?? '')}</output>
        : field.control === 'resource_list' ? <ResourceRows {...root} field={field} />
          : field.control === 'resource_slot' ? <Leaves root={root} objectPath={field.objectPath} fields={field.fields} />
            : <>
              {!field.children.length && <p className={styles.notice}>当前没有消耗子项。</p>}
              {field.children.map(child => <div className={styles.consume} key={child.name}>
                <div className={styles.consumeActions}><button type="button" disabled={locked} aria-label={`移除${child.label}消耗`}
                  onClick={() => void run('consume_remove', { key: child.name }).catch(() => {})}>移除{child.label}消耗</button></div>
                {isResourceField(child) ? <ResourceControl {...root} field={child} objectPath={field.objectPath} />
                  : <Leaves root={root} objectPath={field.objectPath} fields={[child]} />}
              </div>)}
              <ActionMenu label={`添加${field.label}子项`} disabled={locked || !field.addable.length}
                items={field.addable.map(item => ({ id: item.name, label: item.label,
                  run: () => { void run('consume_add', { key: item.name }).catch(() => {}); } }))}>添加消耗子项</ActionMenu>
            </>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {field.inactiveReason && <p className={styles.notice}>{field.inactiveReason}</p>}
    </div>}
  </section>;
}

function ResourceRows(props: ResourceFieldProps & { field: ResourceListField }) {
  const { field } = props;
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const id = useId();
  const listRef = useRef<HTMLDivElement>(null);
  const addRef = useRef<HTMLButtonElement>(null);
  const focus = useRef<string | null | undefined>(undefined);
  const run = (action: string, extra: Record<string, unknown> = {}) => props.onAction(action, { ...extra, objectPath: props.objectPath, field: field.name });
  useEffect(() => {
    if (props.disabled || focus.current === undefined) return;
    const target = focus.current; focus.current = undefined;
    (target ? listRef.current?.querySelector<HTMLButtonElement>(`[data-item-id="${target}"] [data-item-title]`) : addRef.current)?.focus({ preventScroll: true });
  }, [props.disabled, field.rows]);
  async function remove(itemId: string) {
    const index = field.rows.findIndex(row => row.itemId === itemId);
    focus.current = field.rows[index + 1]?.itemId ?? field.rows[index - 1]?.itemId ?? null;
    try { await run('resource_remove', { itemId }); } catch { focus.current = undefined; }
  }
  function move(itemId: string, direction: 'up' | 'down') {
    const beforeItemId = moveBefore(field.rows, itemId, direction);
    if (beforeItemId === undefined) return;
    focus.current = itemId;
    void run('resource_move', { itemId, beforeItemId }).catch(() => { focus.current = undefined; });
  }
  return <div ref={listRef} className={styles.rows}>
    {!field.rows.length && <p className={styles.notice}>当前没有资源项。</p>}
    {field.rows.map((row, index) => {
      const open = !closed[row.itemId];
      const bodyId = `${id}-${row.itemId}`;
      return <section key={row.itemId} data-item-id={row.itemId} className={styles.item}>
        <header className={styles.itemHead}>
          <button type="button" className={styles.title} data-item-title aria-expanded={open} aria-controls={bodyId}
            onClick={() => setClosed(current => ({ ...current, [row.itemId]: open }))}><Fold expanded={open} />第 {index + 1} 项</button>
          <div className={styles.actions}>
            <button type="button" disabled={props.disabled || !field.canMove || index === 0} aria-label={`上移第 ${index + 1} 项`} onClick={() => move(row.itemId, 'up')}>上移</button>
            <button type="button" disabled={props.disabled || !field.canMove || index === field.rows.length - 1} aria-label={`下移第 ${index + 1} 项`} onClick={() => move(row.itemId, 'down')}>下移</button>
            <button type="button" disabled={props.disabled || !field.canRemove} aria-label={`删除第 ${index + 1} 项`} onClick={() => void remove(row.itemId)}>删除</button>
          </div>
        </header>
        {open && <div id={bodyId} className={styles.itemBody}>
          {row.notice ? <p className={styles.notice}>{row.notice}</p> : <Leaves root={props} objectPath={row.objectPath} fields={row.fields} />}
        </div>}
      </section>;
    })}
    <button ref={addRef} type="button" className={styles.add} disabled={props.disabled || !field.canInsert}
      onClick={() => void run('resource_add').catch(() => {})}>添加{field.label}项</button>
  </div>;
}
