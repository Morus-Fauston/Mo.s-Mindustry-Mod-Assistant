import { useEffect, useId, useRef, useState, useSyncExternalStore, type ReactNode } from 'react';
import type { BasicFormProps } from '../forms/BasicForm';
import { ActionMenu } from '../forms/ActionMenu';
import { ContentRefSelector } from '../references/ContentRefSelector';
import { encodeFieldKey, moveBefore } from '../nested/address';
import type { NestedFormPlan, ObjectPath } from '../nested/types';
import { createWeaponController } from './controller';
import { weaponCreationPayload, type WeaponArrayField, type WeaponCreationDraft } from './types';
import styles from './WeaponArray.module.css';

export { findWeaponField } from './address';
export { isWeaponArrayField } from './types';
export type { WeaponArrayField } from './types';
export interface WeaponArrayProps extends Omit<BasicFormProps, 'renderField'> {
  field: WeaponArrayField;
  objectPath: ObjectPath;
  renderForm: (plan: NestedFormPlan) => ReactNode;
}

export function WeaponArray(props: WeaponArrayProps) {
  const owner = JSON.stringify([props.document.sessionId, props.document.path, props.objectPath, props.field.name]);
  return <WeaponArrayBody key={owner} {...props} owner={owner} />;
}

function Fold({ expanded }: { expanded: boolean }) {
  return <svg viewBox="0 0 16 16" aria-hidden="true" data-expanded={expanded}><path d="m6 4 4 4-4 4" /></svg>;
}

function WeaponArrayBody(props: WeaponArrayProps & { owner: string }) {
  const { field } = props;
  const [controller] = useState(createWeaponController);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  const action = useRef(props.onAction); action.current = props.onAction;
  const [expanded, setExpanded] = useState(true);
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const [creating, setCreating] = useState(false);
  const [blankId, setBlankId] = useState<string | null>(null);
  const [draft, setDraft] = useState<WeaponCreationDraft>({ mode: 'reference', reference: null, name: '', bulletType: field.bulletTypes[0]?.value ?? '' });
  const [creationError, setCreationError] = useState('');
  const id = useId();
  const listRef = useRef<HTMLDivElement>(null), addRef = useRef<HTMLButtonElement>(null), blankCancelRef = useRef<HTMLButtonElement>(null);
  const restoreFocus = useRef<string | null | undefined>(undefined);
  const current = state.identity === props.owner;
  const busy = !current || state.pending || props.disabled;
  const locked = busy || field.readOnly || Boolean(field.inactiveReason);
  const blank = field.items.find(item => item.itemId === blankId && item.canCreateBlank);
  const fieldError = props.errors[encodeFieldKey(props.objectPath, field.name)] ?? field.validationError;
  const nameLabel = props.document.fieldNames.name ?? '名称';
  const bulletLabel = `${props.document.fieldNames.bullet ?? '子弹'}${props.document.fieldNames.type ?? '类型'}`;
  const perform = (name: string, payload: Record<string, unknown>) => locked ? Promise.resolve(false) : controller.run(name, payload);
  const run = (name: string, payload: Record<string, unknown> = {}) => perform(name, { ...payload, objectPath: props.objectPath, field: field.name });

  useEffect(() => {
    controller.start(props.owner, (name, payload) => action.current(name, payload));
    return () => controller.stop();
  }, [controller, props.owner]);
  useEffect(() => { if (blank && !busy) blankCancelRef.current?.focus({ preventScroll: true }); }, [blank?.itemId, busy]);
  useEffect(() => {
    if (busy || restoreFocus.current === undefined) return;
    const target = restoreFocus.current; restoreFocus.current = undefined;
    (target ? listRef.current?.querySelector<HTMLButtonElement>(`[data-item-id="${target}"] [data-item-title]`) : addRef.current)?.focus({ preventScroll: true });
  }, [busy, field.items]);

  async function remove(itemId: string) {
    const index = field.items.findIndex(item => item.itemId === itemId);
    restoreFocus.current = field.items[index + 1]?.itemId ?? field.items[index - 1]?.itemId ?? null;
    if (!await run('weapon_remove', { itemId })) restoreFocus.current = undefined;
  }
  function move(itemId: string, direction: 'up' | 'down') {
    const beforeItemId = moveBefore(field.items, itemId, direction);
    if (beforeItemId === undefined) return;
    restoreFocus.current = itemId;
    void run('weapon_move', { itemId, beforeItemId }).then(success => { if (!success) restoreFocus.current = undefined; });
  }
  async function add() {
    if (locked) return;
    setCreationError('');
    let payload: Record<string, unknown>;
    try { payload = weaponCreationPayload(field, props.objectPath, draft); }
    catch (failure) { setCreationError(failure instanceof Error ? failure.message : '武器添加资料无效。'); return; }
    if (await perform('weapon_add', payload)) {
      setCreating(false); setDraft(previous => ({ ...previous, reference: null, name: '' })); restoreFocus.current = null;
      addRef.current?.focus({ preventScroll: true });
    }
  }
  function cancelBlank() {
    if (locked) return;
    restoreFocus.current = blankId; setBlankId(null);
    listRef.current?.querySelector<HTMLButtonElement>(`[data-item-id="${blankId}"] [data-item-title]`)?.focus({ preventScroll: true });
  }
  async function confirmBlank() {
    if (!blank) return;
    if (await perform('weapon_expand', { objectPath: blank.objectPath, allowBlank: true })) {
      restoreFocus.current = blank.itemId; setBlankId(null);
    }
  }

  return <section className={styles.container} data-field={field.name} data-field-type="arr" aria-label={field.label} aria-invalid={Boolean(fieldError)} aria-busy={busy}>
    <header className={styles.heading}>
      <button type="button" className={styles.title} aria-expanded={expanded} aria-controls={id} title={field.help}
        onClick={() => setExpanded(value => !value)}><Fold expanded={expanded} />{field.label}<span className={styles.count}>{field.items.length} 项</span></button>
      {field.deletable && <button type="button" disabled={locked} aria-label={`删除${field.label}字段`}
        onClick={() => void run('delete_field')}>删除字段</button>}
    </header>
    {expanded && <div id={id} className={styles.body} ref={listRef}>
      {field.readOnly ? <output className={styles.notice}>{typeof field.displayValue === 'object' ? JSON.stringify(field.displayValue) : String(field.displayValue ?? '空值')}</output> : <>
        {!field.items.length && <p className={styles.notice}>当前没有武器。</p>}
        {field.items.map((item, index) => {
          const open = !closed[item.itemId], bodyId = `${id}-${item.itemId}`;
          return <section key={item.itemId} className={styles.item} data-item-id={item.itemId} data-weapon-mode={item.mode}>
            <header className={styles.itemHead}>
              <button type="button" className={styles.title} data-item-title aria-expanded={open} aria-controls={bodyId}
                onClick={() => setClosed(previous => ({ ...previous, [item.itemId]: open }))}><Fold expanded={open} />第 {index + 1} 项
                <span className={styles.mode}>{item.mode === 'reference' ? '引用' : item.mode === 'inline' ? '内联' : '原始数据'}</span></button>
              <div className={styles.actions}>
                <button type="button" disabled={locked || !field.canMove || index === 0} aria-label={`上移第 ${index + 1} 项`} onClick={() => move(item.itemId, 'up')}>上移</button>
                <button type="button" disabled={locked || !field.canMove || index === field.items.length - 1} aria-label={`下移第 ${index + 1} 项`} onClick={() => move(item.itemId, 'down')}>下移</button>
                <button type="button" disabled={locked || !field.canRemove} aria-label={`删除第 ${index + 1} 项`} onClick={() => void remove(item.itemId)}>删除</button>
              </div>
            </header>
            {open && <div id={bodyId} className={styles.itemBody}>
              {item.notice && <p className={styles.notice}>{item.notice}</p>}
              {item.form && <fieldset className={styles.formShell} disabled={locked}>{props.renderForm(item.form)}</fieldset>}
              {item.mode === 'reference' && <>
                {Boolean(item.overrideGroups?.length) && <div className={styles.overrides}><span>添加覆盖字段</span>
                  {item.overrideGroups!.map(group => <ActionMenu key={group.id} label={`添加${group.label}覆盖字段`} disabled={locked}
                    items={group.fields.map(choice => ({ id: choice.name, label: choice.label,
                      run: () => { void perform('weapon_add_override', { objectPath: item.objectPath, field: choice.name }); } }))}>{group.label}</ActionMenu>)}
                </div>}
                <div className={styles.actions}>
                  {item.canExpand && <button type="button" disabled={locked} onClick={() => void perform('weapon_expand', { objectPath: item.objectPath })}>展开为内联</button>}
                  {item.canCreateBlank && <button type="button" disabled={locked} onClick={() => setBlankId(item.itemId)}>创建空白内联</button>}
                </div>
                {blank?.itemId === item.itemId && <div className={styles.confirmation} role="group" aria-label="确认创建空白内联"
                  onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); cancelBlank(); } }}>
                  <p>未找到引用的武器定义。确认后将创建带基础子弹的空白内联武器，并保留此项的覆盖字段。</p>
                  <div className={styles.actions}>
                    <button type="button" disabled={locked} onClick={() => void confirmBlank()}>确认创建空白内联</button>
                    <button ref={blankCancelRef} type="button" disabled={locked} onClick={cancelBlank}>取消</button>
                  </div>
                </div>}
              </>}
            </div>}
          </section>;
        })}
        <button ref={addRef} type="button" className={styles.add} disabled={locked || !field.canInsert} aria-expanded={creating} aria-controls={`${id}-create`}
          onClick={() => setCreating(value => !value)}>添加武器</button>
        {creating && <div id={`${id}-create`} className={styles.creation}>
          <fieldset className={styles.modes} disabled={locked}><legend>添加方式</legend>
            <label><input type="radio" name={`${id}-mode`} checked={draft.mode === 'reference'} onChange={() => { setDraft(previous => ({ ...previous, mode: 'reference' })); setCreationError(''); }} />引用已有武器</label>
            <label><input type="radio" name={`${id}-mode`} checked={draft.mode === 'inline'} onChange={() => { setDraft(previous => ({ ...previous, mode: 'inline' })); setCreationError(''); }} />内联新建武器</label>
          </fieldset>
          {draft.mode === 'reference' ? <div className={styles.creationField}>
            <span>{nameLabel}</span><ContentRefSelector label={nameLabel} value={draft.reference} disabled={locked} nullable={false} invalid={Boolean(creationError)}
              load={query => props.onLoadReference(encodeFieldKey(props.objectPath, field.name), query)}
              onSelect={async value => { setDraft(previous => ({ ...previous, reference: value })); setCreationError(''); }} />
          </div> : <>
            <div className={styles.creationField}><label htmlFor={`${id}-name`} title={props.document.fieldDocs.name ?? ''}>{nameLabel}</label>
              <div className={styles.control} data-field-type="str"><input id={`${id}-name`} aria-label={nameLabel} aria-invalid={Boolean(creationError)}
                disabled={locked} value={draft.name} onChange={event => { const name = event.target.value; setDraft(previous => ({ ...previous, name })); setCreationError(''); }} /></div>
            </div>
            <div className={styles.creationField}><label htmlFor={`${id}-bullet`} title={props.document.fieldDocs.bullet ?? ''}>{bulletLabel}</label>
              <div className={styles.control} data-field-type="obj"><select id={`${id}-bullet`} aria-label={bulletLabel} disabled={locked} value={draft.bulletType}
                onChange={event => { const bulletType = event.target.value; setDraft(previous => ({ ...previous, bulletType })); setCreationError(''); }}>
                {field.bulletTypes.map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
              </select></div>
            </div>
          </>}
          {creationError && <p className={styles.error} role="alert">{creationError}</p>}
          <div className={styles.actions}>
            <button type="button" disabled={locked} onClick={() => void add()}>确认添加</button>
            <button type="button" disabled={locked} onClick={() => { setCreating(false); setCreationError(''); addRef.current?.focus({ preventScroll: true }); }}>取消</button>
          </div>
        </div>}
      </>}
      {fieldError && <p className={styles.error} role="alert">{fieldError}</p>}
      {field.inactiveReason && <p className={styles.notice}>{field.inactiveReason}</p>}
      {current && state.error && <p className={styles.error} role="alert">{state.error}</p>}
      {current && state.pending && <p className={styles.notice} role="status">正在提交武器修改…</p>}
    </div>}
  </section>;
}
