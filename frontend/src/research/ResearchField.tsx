import { useEffect, useId, useRef, useState } from 'react';
import { BasicForm, type BasicFormProps } from '../forms/BasicForm';
import type { FormField } from '../forms/types';
import { encodeFieldKey, moveBefore } from '../nested/address';
import type { ObjectPath } from '../nested/types';
import { ContentRefSelector } from '../references/ContentRefSelector';
import { researchLeafProps, type PlanetTarget } from './address';
import type { ResearchCollection, ResearchDescriptor, ResearchSpecialField, PlanetSetDescriptor } from './types';
import styles from './ResearchField.module.css';

export { findResearchField } from './address';
export { isResearchField } from './types';
export type { ResearchDescriptor, PlanetSetDescriptor } from './types';

export interface ResearchFieldProps extends Omit<BasicFormProps, 'renderField'> {
  field: ResearchSpecialField;
  objectPath: ObjectPath;
}

export function ResearchField(props: ResearchFieldProps) {
  const [pending, setPending] = useState(false), [error, setError] = useState('');
  const busy = useRef(false), generation = useRef(0);
  const owner = `${props.document.sessionId}/${props.document.path}`;
  const ownerRef = useRef(owner); ownerRef.current = owner;
  useEffect(() => {
    generation.current++; busy.current = false; setPending(false); setError('');
    return () => { generation.current++; };
  }, [owner]);
  const action: BasicFormProps['onAction'] = async (name, payload) => {
    if (props.disabled || busy.current) throw new Error('正在提交修改，请稍后重试。');
    const current = generation.current;
    busy.current = true; setPending(true); setError('');
    try { await props.onAction(name, payload); }
    catch (failure) {
      if (ownerRef.current === owner && generation.current === current) setError(failure instanceof Error ? failure.message : '研究修改未能完成，请重试。');
      throw failure;
    } finally {
      if (ownerRef.current === owner && generation.current === current) { busy.current = false; setPending(false); }
    }
  };
  return <div className={styles.research} aria-busy={pending}>
    {error && <p className={styles.error} role="alert">{error}</p>}
    <ResearchControl key={owner} {...props} disabled={props.disabled || pending} onAction={action} />
  </div>;
}

function Fold({ expanded }: { expanded: boolean }) {
  return <svg viewBox="0 0 16 16" aria-hidden="true" data-expanded={expanded}><path d="m6 4 4 4-4 4" /></svg>;
}

function RawValue({ value }: { value: unknown }) {
  return <output className={styles.raw}>{value === null ? '空值' : typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')}</output>;
}

function Leaves({ root, objectPath, fields, planet }: {
  root: ResearchFieldProps; objectPath: ObjectPath; fields: FormField[]; planet?: PlanetTarget;
}) {
  return <div className={styles.leaves}><BasicForm {...researchLeafProps(root, objectPath, fields, planet)} /></div>;
}

function ResearchControl(props: ResearchFieldProps) {
  const { field, objectPath } = props;
  const [expanded, setExpanded] = useState(true);
  const id = useId();
  const error = props.errors[encodeFieldKey(objectPath, field.name)] ?? field.validationError;
  const root = { ...props, disabled: props.disabled || field.readOnly || Boolean(field.inactiveReason) };
  return <section className={styles.container} data-field={field.name} data-field-type={field.control === 'planet_set' ? 'arr' : 'ref'}
    aria-label={field.label} aria-invalid={Boolean(error)}>
    <header className={styles.heading}>
      <button type="button" className={styles.title} aria-expanded={expanded} aria-controls={id} title={field.help}
        onClick={() => setExpanded(value => !value)}><Fold expanded={expanded} />{field.label}</button>
      {field.deletable && <button type="button" disabled={props.disabled} aria-label={`删除${field.label}字段`}
        onClick={() => void props.onAction('delete_field', { objectPath, field: field.name }).catch(() => {})}>删除字段</button>}
    </header>
    {expanded && <div id={id} className={styles.body}>
      {field.readOnly ? <RawValue value={field.displayValue} /> : field.control === 'research'
        ? <ResearchContents {...root} field={field} /> : <PlanetRows {...root} field={field} />}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {field.inactiveReason && <p className={styles.notice}>{field.inactiveReason}</p>}
    </div>}
  </section>;
}

function ResearchContents(props: ResearchFieldProps & { field: ResearchDescriptor }) {
  const moreFields = props.field.fields.filter(field => field.name !== 'parent');
  const [more, setMore] = useState(() => moreFields.some(field => field.present));
  const id = useId();
  return <>
    <Leaves root={props} objectPath={props.field.objectPath} fields={props.field.fields.filter(field => field.name === 'parent')} />
    {props.field.requirements && <ResearchRows root={props} collection={props.field.requirements} />}
    {props.field.objectives && <ResearchRows root={props} collection={props.field.objectives} />}
    <button className={styles.more} type="button" aria-expanded={more} aria-controls={id} onClick={() => setMore(value => !value)}>
      <Fold expanded={more} />{more ? '收起更多科技树设置' : '显示更多科技树设置'}</button>
    {more && <div id={id}><Leaves root={props} objectPath={props.field.objectPath} fields={moreFields} /></div>}
  </>;
}

function ResearchRows({ root, collection }: { root: ResearchFieldProps; collection: ResearchCollection }) {
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const id = useId(), list = useRef<HTMLDivElement>(null), add = useRef<HTMLButtonElement>(null);
  const focus = useRef<string | null | undefined>(undefined);
  const [expanded, setExpanded] = useState(true);
  const locked = root.disabled || collection.readOnly;
  const error = root.errors[encodeFieldKey(root.field.objectPath, collection.name)] ?? collection.validationError;
  useEffect(() => {
    const ids = new Set(collection.rows.map(row => row.itemId));
    setClosed(previous => Object.keys(previous).some(key => !ids.has(key))
      ? Object.fromEntries(Object.entries(previous).filter(([key]) => ids.has(key))) : previous);
    setRowErrors(previous => Object.keys(previous).some(key => !ids.has(key))
      ? Object.fromEntries(Object.entries(previous).filter(([key]) => ids.has(key))) : previous);
    if (locked || focus.current === undefined) return;
    const target = focus.current; focus.current = undefined;
    (target ? list.current?.querySelector<HTMLButtonElement>(`[data-item-id="${target}"] [data-item-title]`) : add.current)?.focus({ preventScroll: true });
  }, [collection.rows, locked]);
  const run = (action: string, extra: Record<string, unknown> = {}) => root.onAction(action,
    { ...extra, objectPath: root.objectPath, field: root.field.name, collection: collection.name });
  async function rowAction(itemId: string, action: string, extra: Record<string, unknown> = {}) {
    setRowErrors(previous => ({ ...previous, [itemId]: '' }));
    try { await run(action, { ...extra, itemId }); }
    catch (failure) {
      if (alive.current) setRowErrors(previous => ({ ...previous, [itemId]: failure instanceof Error ? failure.message : '此项修改未能完成，请重试。' }));
      throw failure;
    }
  }
  async function remove(itemId: string) {
    const index = collection.rows.findIndex(row => row.itemId === itemId);
    focus.current = collection.rows[index + 1]?.itemId ?? collection.rows[index - 1]?.itemId ?? null;
    try { await rowAction(itemId, 'research_remove'); } catch { focus.current = undefined; }
  }
  function move(itemId: string, direction: 'up' | 'down') {
    const beforeItemId = moveBefore(collection.rows, itemId, direction);
    if (beforeItemId === undefined) return;
    focus.current = itemId;
    void rowAction(itemId, 'research_move', { beforeItemId }).catch(() => { focus.current = undefined; });
  }
  return <section className={styles.collection} data-field={collection.name} data-field-type="arr" aria-invalid={Boolean(error)}>
    <header className={styles.heading}>
      <button type="button" className={styles.title} aria-expanded={expanded} aria-controls={id} title={collection.help}
        onClick={() => setExpanded(value => !value)}><Fold expanded={expanded} />{collection.label}<span className={styles.count}>{collection.rows.length} 项</span></button>
    </header>
    {expanded && <div className={styles.body} ref={list} id={id}>
      {collection.readOnly ? <RawValue value={collection.value} /> : <>
        {!collection.rows.length && <p className={styles.notice}>当前没有{collection.label}。</p>}
        {collection.rows.map((row, index) => {
          const open = !closed[row.itemId], rowId = `${id}-${row.itemId}`;
          const type = row.typeSelector, selectedKnown = type?.choices.some(choice => choice.value === type.value);
          const typeLabel = root.document.fieldNames['objective.type'] ?? root.document.fieldNames.type ?? '类型';
          const rowError = rowErrors[row.itemId] || root.errors[encodeFieldKey(row.objectPath, 'type')];
          return <section key={row.itemId} className={styles.item} data-item-id={row.itemId} aria-invalid={Boolean(rowError)}>
            <header className={styles.itemHead}>
              <button type="button" className={styles.title} data-item-title aria-expanded={open} aria-controls={rowId}
                onClick={() => setClosed(current => ({ ...current, [row.itemId]: open }))}><Fold expanded={open} />第 {index + 1} 项</button>
              <div className={styles.actions}>
                <button type="button" disabled={locked || !collection.canMove || index === 0} aria-label={`上移第 ${index + 1} 项`} onClick={() => move(row.itemId, 'up')}>上移</button>
                <button type="button" disabled={locked || !collection.canMove || index === collection.rows.length - 1} aria-label={`下移第 ${index + 1} 项`} onClick={() => move(row.itemId, 'down')}>下移</button>
                <button type="button" disabled={locked || !collection.canRemove} aria-label={`删除第 ${index + 1} 项`} onClick={() => void remove(row.itemId)}>删除</button>
              </div>
            </header>
            {open && <div id={rowId} className={styles.itemBody}>
              {type && <div className={styles.typeRow} data-field="type" data-field-type="str">
                <label htmlFor={`${rowId}-type`}>{typeLabel}</label>
                <select id={`${rowId}-type`} aria-label={typeLabel} title={root.document.fieldDocs['objective.type'] ?? ''}
                  value={type.value ?? ''} disabled={locked} aria-invalid={Boolean(rowError)}
                  onChange={event => void rowAction(row.itemId, 'research_objective_type', { type: event.target.value }).catch(() => {})}>
                  {!selectedKnown && <option value={type.value ?? ''} disabled>{type.value ? `未识别类型：${type.value}` : '未写入目标类型'}</option>}
                  {type.choices.map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
                </select>
              </div>}
              {row.notice && <><p className={styles.notice}>{row.notice}</p><RawValue value={row.value} /></>}
              <Leaves root={{ ...root, disabled: locked }} objectPath={row.objectPath} fields={row.fields} />
              {rowError && <p className={styles.error} role="alert">{rowError}</p>}
            </div>}
          </section>;
        })}
        <button type="button" ref={add} className={styles.add} disabled={locked || !collection.canInsert}
          onClick={() => void run('research_add').catch(() => {})}>添加{collection.label}</button>
      </>}
      {error && <p className={styles.error} role="alert">{error}</p>}
    </div>}
  </section>;
}

function PlanetRows(props: ResearchFieldProps & { field: PlanetSetDescriptor }) {
  const { field } = props;
  const list = useRef<HTMLDivElement>(null), focus = useRef<string | null | undefined>(undefined);
  const lastItemFallback = useRef<HTMLButtonElement | null>(null);
  useEffect(() => () => {
    if (focus.current === null && lastItemFallback.current?.isConnected) lastItemFallback.current.focus({ preventScroll: true });
  }, []);
  useEffect(() => {
    if (props.disabled || focus.current === undefined) return;
    const target = focus.current; focus.current = undefined;
    list.current?.querySelector<HTMLButtonElement>(target
      ? `[data-item-id="${target}"] [data-reference-selector] > button`
      : '[data-add-planet] [data-reference-selector] > button')?.focus({ preventScroll: true });
  }, [props.disabled, field.rows]);
  async function remove(itemId: string) {
    const index = field.rows.findIndex(row => row.itemId === itemId);
    focus.current = field.rows[index + 1]?.itemId ?? field.rows[index - 1]?.itemId ?? null;
    if (focus.current === null) lastItemFallback.current = list.current?.closest('[data-group]')?.querySelector<HTMLButtonElement>('button[aria-expanded]') ?? null;
    try { await props.onAction('planet_remove', { objectPath: props.objectPath, field: field.name, itemId }); }
    catch { focus.current = undefined; }
  }
  return <div ref={list} className={styles.rows}>
    {!field.rows.length && <p className={styles.notice}>当前没有选择星球。</p>}
    {field.rows.map((row, index) => <section className={styles.planet} data-item-id={row.itemId} key={row.itemId}>
      <Leaves root={props} objectPath={row.objectPath} fields={row.fields}
        planet={{ objectPath: props.objectPath, field: field.name, itemId: row.itemId }} />
      <button type="button" disabled={props.disabled || !field.canRemove} aria-label={`删除第 ${index + 1} 个星球`}
        onClick={() => void remove(row.itemId)}>删除</button>
    </section>)}
    {field.addField && <div className={styles.planetAdd} data-add-planet>
      <span>添加{field.addField.label}</span>
      <ContentRefSelector label={`添加${field.addField.label}`} value={null} nullable={false}
        disabled={props.disabled || !field.canInsert}
        load={query => props.onLoadReference(encodeFieldKey(field.objectPath, field.addField!.name), query)}
        onSelect={value => props.onAction('planet_add', { objectPath: props.objectPath, field: field.name, value })} />
    </div>}
  </div>;
}
