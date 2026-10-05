import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import type { TreeNode } from './types';
import { ancestorIds, expandedGroups, filterTree, flattenTree, type TreeRow } from './tree';
import styles from './ProjectTree.module.css';

interface ProjectTreeProps {
  nodes: TreeNode[];
  selectedPath: string | null;
  onOpen: (node: TreeNode) => void;
}

function NodeIcon({ kind }: { kind: TreeNode['kind'] }) {
  return <svg className={styles.icon} viewBox="0 0 16 16" aria-hidden="true">
    {kind === 'group' ? <path d="M1.8 4.5V3h4l1.4 1.5h7v8h-12z" /> : kind === 'sprite' ? <>
      <rect x="2.5" y="2.5" width="11" height="11" rx="1" />
      <path d="m3 11 3-3 2.2 2 2-3 3 4" /><circle cx="6" cy="5.5" r=".7" />
    </> : <><path d="M4 1.8h5l3 3v9.4H4zM9 2v3h3M6 8h4M6 10.5h4" /></>}
  </svg>;
}

export function ProjectTree({ nodes, selectedPath, onOpen }: ProjectTreeProps) {
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState(() => new Set(nodes.filter(node => node.kind === 'group').map(node => node.id)));
  const [searchCollapsed, setSearchCollapsed] = useState(new Set<string>());
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const beforeSearch = useRef<string | null>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const searching = Boolean(query.trim());
  const filtered = useMemo(() => filterTree(nodes, query), [nodes, query]);
  const visibleExpanded = useMemo(() => searching
    ? new Set([...expandedGroups(filtered)].filter(id => !searchCollapsed.has(id)))
    : expanded, [searching, filtered, searchCollapsed, expanded]);
  const rows = useMemo(() => flattenTree(filtered, visibleExpanded), [filtered, visibleExpanded]);
  const activeId = rows.some(row => row.node.id === focusedId) ? focusedId : rows[0]?.node.id;

  useEffect(() => {
    // Search is a temporary view; opening a result must not rewrite its saved folds.
    if (!selectedPath || searching) return;
    setExpanded(previous => new Set([...previous, ...ancestorIds(nodes, selectedPath)]));
  }, [nodes, selectedPath]);

  function focusRow(id: string | undefined | null) {
    if (!id) return;
    setFocusedId(id);
    requestAnimationFrame(() => {
      const button = buttons.current.get(id);
      button?.focus({ preventScroll: true });
      button?.scrollIntoView({ block: 'nearest' });
    });
  }

  function changeSearch(value: string) {
    if (!searching && value.trim()) {
      beforeSearch.current = activeId ?? null;
      setSearchCollapsed(new Set());
    }
    setQuery(value);
    if (!value.trim()) setFocusedId(beforeSearch.current);
  }

  function clearSearch(returnToTree = false) {
    setQuery('');
    setFocusedId(beforeSearch.current);
    setSearchCollapsed(new Set());
    if (returnToTree) focusRow(beforeSearch.current ?? nodes[0]?.id);
    else searchInput.current?.focus();
  }

  function toggle(node: TreeNode) {
    if (searching) {
      setSearchCollapsed(previous => {
        const next = new Set(previous);
        if (next.has(node.id)) next.delete(node.id); else next.add(node.id);
        return next;
      });
    } else {
      setExpanded(previous => {
        const next = new Set(previous);
        if (next.has(node.id)) next.delete(node.id); else next.add(node.id);
        return next;
      });
    }
  }

  function activate(node: TreeNode) {
    setFocusedId(node.id);
    if (node.kind === 'group') toggle(node); else onOpen(node);
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, row: TreeRow, index: number) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    switch (event.key) {
      case 'ArrowDown': focusRow(rows[Math.min(index + 1, rows.length - 1)]?.node.id); break;
      case 'ArrowUp': focusRow(rows[Math.max(index - 1, 0)]?.node.id); break;
      case 'Home': focusRow(rows[0]?.node.id); break;
      case 'End': focusRow(rows.at(-1)?.node.id); break;
      case 'ArrowRight':
        if (row.node.kind === 'group') {
          if (!visibleExpanded.has(row.node.id)) toggle(row.node);
          else if (rows[index + 1]?.parentId === row.node.id) focusRow(rows[index + 1].node.id);
        }
        break;
      case 'ArrowLeft':
        if (row.node.kind === 'group' && visibleExpanded.has(row.node.id)) toggle(row.node);
        else focusRow(row.parentId);
        break;
      case 'Enter': case ' ': activate(row.node); break;
      case 'Escape': if (searching) clearSearch(true); else return; break;
      default: return;
    }
    event.preventDefault();
  }

  return <div className={styles.projectTree}>
    <div className={styles.search}>
      <input ref={searchInput} aria-label="搜索文件" placeholder="搜索显示名或名称" value={query}
        onChange={event => changeSearch(event.target.value)}
        onKeyDown={event => {
          if (event.key === 'Escape' && query) { event.preventDefault(); clearSearch(); }
          if (event.key === 'ArrowDown') { event.preventDefault(); focusRow(activeId); }
        }} />
      {query && <button className={styles.clear} type="button" aria-label="清空搜索" title="清空搜索（Esc）"
        onMouseDown={event => event.preventDefault()} onClick={() => clearSearch()}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4.5 4.5 7 7m0-7-7 7" /></svg>
      </button>}
    </div>
    <div className={styles.tree} role="tree" aria-label="工程文件" aria-multiselectable="false">
      {rows.map((row, index) => <button key={row.node.id} type="button" role="treeitem"
        ref={element => { if (element) buttons.current.set(row.node.id, element); else buttons.current.delete(row.node.id); }}
        className={styles.row} tabIndex={row.node.id === activeId ? 0 : -1}
        aria-level={row.depth + 1} aria-posinset={row.position} aria-setsize={row.siblings}
        aria-selected={Boolean(row.node.path && row.node.path === selectedPath)}
        aria-expanded={row.node.kind === 'group' ? visibleExpanded.has(row.node.id) : undefined}
        data-node-id={row.node.id} data-node-kind={row.node.kind} data-path={row.node.path}
        title={[row.node.label, row.node.name, row.node.path, row.node.error].filter(Boolean).join('\n')}
        onFocus={() => setFocusedId(row.node.id)} onClick={() => activate(row.node)}
        onKeyDown={event => onKeyDown(event, row, index)}>
        <span className={styles.indents} aria-hidden="true">{Array.from({ length: row.depth }, (_, depth) =>
          <span className={styles.indent} key={depth} />)}</span>
        <span className={styles.chevron} aria-hidden="true">{row.node.kind === 'group' &&
          <svg viewBox="0 0 16 16"><path d={visibleExpanded.has(row.node.id) ? 'm4.5 6.5 3.5 3.5 3.5-3.5' : 'm6.5 4.5 3.5 3.5-3.5 3.5'} /></svg>}</span>
        <NodeIcon kind={row.node.kind} />
        <span className={styles.label}>{row.node.label}</span>
        {row.node.error && <span className={styles.error} aria-label="读取异常">!</span>}
      </button>)}
      {rows.length === 0 && <p className={styles.empty} role="status">{searching ? '没有匹配的文件' : '工程中暂无可显示的内容'}</p>}
    </div>
  </div>;
}
