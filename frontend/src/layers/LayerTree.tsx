import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from 'react';
import { FieldControl } from '../forms/BasicForm';
import type { FormDrafts, FormErrors } from '../forms/types';
import { encodeFieldKey } from '../nested/address';
import { canToggleLayer, flattenLayers, layerAncestors, layerKeyAction } from './view';
import type { LayerNode, WeaponAnchor } from './types';
import styles from './LayerTree.module.css';

export type { LayerNode, LayerViewState, WeaponAnchor } from './types';
export { reconcileLayerView, revealLayerView } from './view';

export interface LayerTreeProps {
  sessionId: string;
  path: string;
  nodes: LayerNode[];
  selectedId: string | null;
  revealToken?: number;
  hiddenIds: string[];
  closedIds: string[];
  disabled: boolean;
  drafts: FormDrafts;
  errors: FormErrors;
  fieldNames: Record<string, string>;
  fieldDocs: Record<string, string>;
  onSelect: (id: string) => void;
  onVisibility: (id: string, visible: boolean) => void;
  onExpanded: (id: string, expanded: boolean) => void;
  onRevealParameters: (anchor: WeaponAnchor) => void;
  onDraft: (key: string, text: string) => void;
  onCommit: (key: string) => Promise<void>;
  onReset: (key: string) => void;
  onComposition: (key: string, active: boolean) => void;
}

function Coordinates({ node, props }: { node: LayerNode; props: LayerTreeProps }) {
  if (!node.weapon) return null;
  return <div className={styles.coordinates} role="group" aria-label={`${node.label}安装坐标`}>
    {(['x', 'y'] as const).map(name => {
      const source = node.weapon!.coordinates[name];
      if (!source) return null;
      const key = encodeFieldKey(node.weapon!.objectPath, name);
      // Only coordinate text editing is exposed here. FieldControl owns IME,
      // Enter/blur/Escape and error presentation; Python owns numeric parsing.
      const field = { ...source, name, label: props.fieldNames[name] ?? source.label,
        help: props.fieldDocs[name] ?? source.help, nullable: false, deletable: false,
        readOnly: source.readOnly || source.control !== 'number' };
      return <div className={styles.coordinateCell} key={name} data-coordinate-key={key}>
        <FieldControl field={field} drafts={Object.hasOwn(props.drafts, key) ? { [name]: props.drafts[key] } : {}}
          error={props.errors[key] ?? field.validationError} disabled={props.disabled}
          onDraft={(_, text) => props.onDraft(key, text)} onCommit={() => props.onCommit(key)}
          onReset={() => props.onReset(key)} onComposition={(_, active) => props.onComposition(key, active)}
          onAction={async () => { throw new Error('图层坐标只支持数值输入。'); }}
          onLoadReference={async () => { throw new Error('安装坐标不是引用字段。'); }} />
      </div>;
    })}
  </div>;
}

function Chevron({ expanded }: { expanded: boolean }) {
  return <svg viewBox="0 0 16 16" aria-hidden="true"><path d={expanded ? 'm4.5 6.5 3.5 3.5 3.5-3.5' : 'm6.5 4.5 3.5 3.5-3.5 3.5'} /></svg>;
}

function Visibility({ node, visible, onChange }: { node: LayerNode; visible: boolean; onChange: (visible: boolean) => void }) {
  return <span className={styles.checkbox} data-field-type="bool">
    <input type="checkbox" checked={visible} aria-label={`显示${node.label}图层`} onChange={event => onChange(event.target.checked)} />
    <span className={styles.checkboxFace} aria-hidden="true"><svg viewBox="0 0 14 14">{visible && <path d="m3 7 2.5 2.5L11 4" />}</svg></span>
  </span>;
}

const statusLabels: Record<NonNullable<LayerNode['status']>, string> = { ready: '有', missing: '缺失', optional: '可选', invalid: '异常' };

export function LayerTree(props: LayerTreeProps) {
  return <LayerTreeBody key={JSON.stringify([props.sessionId, props.path])} {...props} />;
}

function LayerTreeBody(props: LayerTreeProps) {
  const rows = flattenLayers(props.nodes, props.closedIds);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const elements = useRef(new Map<string, HTMLDivElement>());
  const revealSelection = useRef<string | null | undefined>(undefined);
  const pendingScroll = useRef<string | null>(null);
  const activeId = rows.some(row => row.node.id === focusedId) ? focusedId
    : rows.some(row => row.node.id === props.selectedId) ? props.selectedId : rows[0]?.node.id;

  useEffect(() => {
    const request = `${props.selectedId}:${props.revealToken ?? ''}`;
    if (request === revealSelection.current) return;
    if (!props.selectedId) { revealSelection.current = null; pendingScroll.current = null; return; }
    const ancestors = layerAncestors(props.nodes, props.selectedId);
    if (!ancestors) return;
    revealSelection.current = request;
    pendingScroll.current = props.selectedId;
    for (const id of ancestors) if (props.closedIds.includes(id)) props.onExpanded(id, true);
    // Selection reveals the row without stealing focus from the parameter input.
    const element = elements.current.get(props.selectedId);
    if (element) { element.scrollIntoView({ block: 'nearest' }); pendingScroll.current = null; }
  }, [props.selectedId, props.revealToken, props.nodes, props.closedIds, props.onExpanded]);

  useLayoutEffect(() => {
    if (!pendingScroll.current) return;
    const element = elements.current.get(pendingScroll.current);
    if (element) { element.scrollIntoView({ block: 'nearest' }); pendingScroll.current = null; }
  });

  function focusRow(id: string) {
    setFocusedId(id);
    const element = elements.current.get(id);
    element?.focus({ preventScroll: true });
    element?.scrollIntoView({ block: 'nearest' });
  }

  function keyDown(event: KeyboardEvent<HTMLDivElement>, id: string) {
    if (event.target !== event.currentTarget || event.altKey || event.ctrlKey || event.metaKey || event.nativeEvent.isComposing) return;
    const action = layerKeyAction(rows, id, event.key, props.closedIds);
    if (!action) return;
    event.preventDefault(); event.stopPropagation();
    if (action.kind === 'focus') focusRow(action.id);
    else if (action.kind === 'expanded') props.onExpanded(action.id, action.expanded);
    else if (action.kind === 'visibility') props.onVisibility(action.id, props.hiddenIds.includes(action.id));
    else props.onSelect(action.id);
  }

  return <div className={styles.tree} role="tree" aria-label="精灵图图层" aria-multiselectable="false">
    {rows.map(row => {
      const { node } = row, expanded = !props.closedIds.includes(node.id), visible = !props.hiddenIds.includes(node.id);
      return <div key={node.id} className={styles.item} role="treeitem" tabIndex={activeId === node.id ? 0 : -1}
        ref={element => { if (element) elements.current.set(node.id, element); else elements.current.delete(node.id); }}
        style={{ '--layer-depth': row.depth } as CSSProperties} aria-label={node.label}
        aria-level={row.depth + 1} aria-posinset={row.position} aria-setsize={row.siblings}
        aria-selected={props.selectedId === node.id} aria-expanded={node.children ? expanded : undefined}
        aria-checked={canToggleLayer(node) ? visible : undefined} data-layer-id={node.id} data-layer-kind={node.kind}
        onFocus={event => { if (event.target === event.currentTarget) setFocusedId(node.id); }}
        onKeyDown={event => keyDown(event, node.id)}>
        <div className={styles.row}>
          <span className={styles.indents} aria-hidden="true">{Array.from({ length: row.depth }, (_, index) => <span className={styles.indent} key={index} />)}</span>
          {node.children ? <button type="button" className={styles.chevron} aria-label={`${expanded ? '折叠' : '展开'}${node.label}`}
            aria-expanded={expanded} onClick={() => props.onExpanded(node.id, !expanded)}><Chevron expanded={expanded} /></button>
            : <span className={styles.chevron} aria-hidden="true" />}
          {canToggleLayer(node) && <Visibility node={node} visible={visible} onChange={value => props.onVisibility(node.id, value)} />}
          <button type="button" className={styles.select} aria-label={`选择${node.label}图层`} title={node.label}
            onClick={() => { props.onSelect(node.id); focusRow(node.id); }}>{node.label}</button>
          {node.status && <span className={styles.status} data-status={node.status}>{statusLabels[node.status]}</span>}
          {node.weapon && <button type="button" className={styles.locate} disabled={props.disabled}
            aria-label={`定位${node.label}参数`} title="定位安装参数" onClick={() => {
              props.onSelect(node.id);
              props.onRevealParameters({ sessionId: props.sessionId, path: props.path,
                itemId: node.weapon!.itemId, objectPath: node.weapon!.objectPath });
            }}><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M9 3 4 8l5 5M4 8h9" /></svg></button>}
        </div>
        {node.weapon && <Coordinates node={node} props={props} />}
        {node.notice && <p className={styles.notice} data-status={node.status}>{node.notice}</p>}
      </div>;
    })}
    {!rows.length && <p className={styles.empty} role="status">当前内容没有图层。</p>}
  </div>;
}
