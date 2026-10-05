import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { createPortal } from 'react-dom';
import { createLatestRequest, moveCandidateIndex, popupGeometry } from './presentation';
import type { PopupGeometry } from './presentation';
import type { ReferenceCandidate, ReferenceResult } from './types';
import styles from './ContentRefSelector.module.css';

export type { ReferenceCandidate, ReferenceResult } from './types';
export interface ContentRefSelectorProps {
  label: string;
  value: string | null;
  disabled: boolean;
  nullable: boolean;
  invalid?: boolean;
  load: (query: string) => Promise<ReferenceResult>;
  onSelect: (value: string | null) => Promise<void>;
}

/** Presentation only: all candidates, allowed categories and values come from Python. */
export function ContentRefSelector({ label, value, disabled, nullable, invalid = false, load, onSelect }: ContentRefSelectorProps) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const headers = useRef(new Map<string, HTMLDivElement>());
  const anchor = useRef<{ top: number; left: number } | null>(null);
  const restoreFocus = useRef(false);
  const loadRef = useRef(load), selectRef = useRef(onSelect);
  loadRef.current = load; selectRef.current = onSelect;
  const [requests] = useState(createLatestRequest);
  const alive = useRef(true), composing = useRef(false), selecting = useRef(false);
  const generation = useRef(0);
  const [position, setPosition] = useState<PopupGeometry | null>(null);
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<ReferenceResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [active, setActive] = useState(-1);
  const [visibleGroup, setVisibleGroup] = useState(0);
  const open = position !== null;

  const close = useCallback((restore = true) => {
    generation.current++; requests.invalidate(); composing.current = false;
    setPosition(null); setLoading(false); setQuery(''); setActive(-1);
    restoreFocus.current = restore;
    if (restore && trigger.current && !trigger.current.disabled) {
      trigger.current.focus({ preventScroll: true }); restoreFocus.current = false;
    }
  }, [requests]);

  const read = useCallback(async (text: string) => {
    setLoading(true); setError(''); setActive(-1);
    try {
      const response = await requests.run(() => loadRef.current(text));
      if (!response.current) return;
      setResult(response.value); setVisibleGroup(0); setLoading(false);
      if (list.current) list.current.scrollTop = 0;
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : '候选内容读取失败，请重试。');
      setResult(null); setLoading(false);
    }
  }, [requests]);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; generation.current++; requests.invalidate(); };
  }, [requests]);

  useEffect(() => {
    close(selecting.current || restoreFocus.current); setResult(null);
    void read('');
    return () => requests.invalidate();
  }, [value, close, read, requests]);

  useEffect(() => { if (disabled) close(false); }, [disabled, close]);

  useEffect(() => {
    if (restoreFocus.current && !saving && !disabled) {
      trigger.current?.focus({ preventScroll: true }); restoreFocus.current = false;
    }
  }, [saving, disabled]);

  useEffect(() => {
    if (!open) return;
    // Immediately retire old search results; debounce only the next read.
    requests.invalidate(); setLoading(true); setActive(-1);
    const timer = window.setTimeout(() => { if (!composing.current) void read(query); }, 120);
    return () => { window.clearTimeout(timer); requests.invalidate(); };
  }, [open, query, read, requests]);

  useEffect(() => {
    if (!open) return;
    search.current?.focus({ preventScroll: true });
    const outside = (event: PointerEvent) => {
      if (!panel.current?.contains(event.target as Node) && !trigger.current?.contains(event.target as Node)) close(false);
    };
    const resize = () => close(false);
    const scroll = (event: Event) => {
      if (panel.current?.contains(event.target as Node)) return;
      const bounds = trigger.current?.getBoundingClientRect();
      if (bounds && anchor.current && (Math.abs(bounds.top - anchor.current.top) > .5 ||
          Math.abs(bounds.left - anchor.current.left) > .5)) close(false);
    };
    document.addEventListener('pointerdown', outside);
    window.addEventListener('resize', resize);
    window.addEventListener('scroll', scroll, true);
    return () => {
      document.removeEventListener('pointerdown', outside);
      window.removeEventListener('resize', resize);
      window.removeEventListener('scroll', scroll, true);
    };
  }, [open, close]);

  const groups = useMemo(() => {
    if (!result) return [];
    return result.categories.map(category => ({ ...category,
      candidates: result.candidates.filter(candidate => candidate.category === category.id) })).filter(group => group.candidates.length);
  }, [result]);
  const candidates = useMemo(() => groups.flatMap(group => group.candidates), [groups]);

  function show() {
    if (disabled || selecting.current) return;
    if (open) { close(); return; }
    setQuery(''); setError(''); setActive(-1); setVisibleGroup(0);
    const bounds = trigger.current!.getBoundingClientRect();
    anchor.current = { top: bounds.top, left: bounds.left };
    setPosition(popupGeometry(bounds, window.innerWidth, window.innerHeight));
  }

  async function choose(next: string | null) {
    if (disabled || selecting.current || composing.current) return;
    selecting.current = true; setSaving(true); setError('');
    const current = generation.current;
    try {
      await selectRef.current(next);
      if (alive.current && current === generation.current) close();
    } catch (failure) {
      if (alive.current && current === generation.current) setError(failure instanceof Error ? failure.message : '引用未能保存，请重试。');
    } finally {
      selecting.current = false;
      if (alive.current) setSaving(false);
    }
  }

  function move(direction: number) {
    if (loading || saving) return;
    const next = moveCandidateIndex(active, direction, candidates.length);
    setActive(next);
    list.current?.querySelector<HTMLElement>(`[data-candidate-index="${next}"]`)?.scrollIntoView({ block: 'nearest' });
  }

  function keyboard(event: KeyboardEvent<HTMLDivElement>) {
    if (composing.current || event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) return;
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); }
    else if (event.key === 'Tab') {
      // Keep every search, bookmark and clear action reachable by keyboard.
      // Escape/cancel returns to the field; Tab stays within this open dialog.
      const controls = [...event.currentTarget.querySelectorAll<HTMLElement>('input:not(:disabled),button:not(:disabled)')]
        .filter(control => control.tabIndex >= 0);
      const boundary = event.shiftKey ? controls[0] : controls.at(-1);
      if (document.activeElement === boundary) {
        event.preventDefault();
        (event.shiftKey ? controls.at(-1) : controls[0])?.focus({ preventScroll: true });
      }
    } else if (event.target === search.current && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
      event.preventDefault(); move(event.key === 'ArrowDown' ? 1 : -1);
    } else if (event.target === search.current && event.key === 'Enter') {
      event.preventDefault(); event.stopPropagation();
      if (!loading && candidates[active]) void choose(candidates[active].value);
    }
  }

  function updateVisibleGroup() {
    if (!list.current) return;
    const top = list.current.getBoundingClientRect().top;
    let current = 0;
    groups.forEach((group, index) => {
      const header = headers.current.get(group.id);
      if (header && header.getBoundingClientRect().top <= top + 1) current = index;
    });
    setVisibleGroup(current);
  }

  function jump(index: number) {
    const header = headers.current.get(groups[index]?.id);
    if (!list.current || !header) return;
    const delta = header.getBoundingClientRect().top - list.current.getBoundingClientRect().top;
    list.current.scrollTop += delta;
    setVisibleGroup(index);
    setActive(groups.slice(0, index).reduce((count, group) => count + group.candidates.length, 0));
    search.current?.focus({ preventScroll: true });
  }

  const current = result?.current.value === value ? result.current : null;
  const currentText = current?.label || (value === null ? '空值' : value || '未选择');
  const unknown = Boolean(value) && current?.known === false;
  const bookmarks = (before: boolean) => groups.map((group, index) => ({ group, index }))
    .filter(({ index }) => before ? index < visibleGroup : index > visibleGroup)
    .map(({ group, index }) => <button type="button" key={group.id} disabled={loading || saving}
      title={`跳转到${group.label}`} onClick={() => jump(index)}>{before ? '上方：' : '下方：'}{group.label}</button>);

  return <div className={styles.root} data-reference-selector="true" data-field-type="ref">
    <button ref={trigger} type="button" className={styles.trigger} disabled={disabled || saving}
      aria-label={label} aria-invalid={invalid} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? id : undefined}
      title={unknown ? `未知引用：${value}，原值已保留` : currentText} onClick={show}
      onKeyDown={event => { if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); if (!open) show(); } }}>
      <span className={styles.currentText}>{currentText}{unknown && <span className={styles.unknown}>（未知引用）</span>}</span>
      <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
    </button>
    {!open && error && <p className={styles.error} role="alert">{error}</p>}
    {position && createPortal(<div ref={panel} id={id} className={styles.popup} style={position}
      role="dialog" aria-label={`选择${label}`} onKeyDown={keyboard}
      onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node) && event.relatedTarget !== trigger.current) close(false); }}>
      <div className={styles.current} title={currentText}>当前：{currentText}{unknown ? '（未知引用，原值保留）' : ''}</div>
      <div className={styles.searchRow}>
        <input ref={search} className={styles.search} aria-label={`搜索${label}`} placeholder="搜索中文或英文标识"
          role="combobox" aria-expanded="true" aria-controls={`${id}-list`} aria-autocomplete="list"
          aria-activedescendant={active >= 0 && !loading ? `${id}-option-${active}` : undefined}
          disabled={saving} value={query} onChange={event => setQuery(event.target.value)}
          onCompositionStart={() => { composing.current = true; requests.invalidate(); setLoading(true); setActive(-1); }}
          onCompositionEnd={event => { composing.current = false; setQuery(event.currentTarget.value); void read(event.currentTarget.value); }} />
        <button type="button" className={styles.tool} aria-label="清空搜索" title="清空搜索，不改变引用值" disabled={!query || saving}
          onClick={() => { setQuery(''); search.current?.focus({ preventScroll: true }); }}>清空搜索</button>
      </div>
      {error && <div className={styles.problem} role="alert"><span>{error}</span>
        <button type="button" className={styles.tool} disabled={saving} onClick={() => void read(query)}>重试</button></div>}
      <nav className={styles.bookmarks} aria-label="上方分类书签">{!loading && bookmarks(true)}</nav>
      <div className={styles.sticky} data-current-category={groups[visibleGroup]?.id ?? ''}>
        {loading ? '正在读取候选内容…' : groups[visibleGroup]?.label ?? '候选内容'}
      </div>
      <div ref={list} id={`${id}-list`} className={styles.list} role="listbox" aria-label={`${label}候选`} aria-busy={loading}
        onScroll={updateVisibleGroup}>
        {!loading && groups.map((group, groupIndex) => {
          const start = groups.slice(0, groupIndex).reduce((count, previous) => count + previous.candidates.length, 0);
          return <div key={group.id} role="group" aria-label={group.label} className={styles.group}>
            <div ref={element => { if (element) headers.current.set(group.id, element); else headers.current.delete(group.id); }}
              className={styles.groupHeader}>{group.label}</div>
            {group.candidates.map((candidate: ReferenceCandidate, index: number) => <button key={`${candidate.value}:${index}`}
              id={`${id}-option-${start + index}`} type="button" role="option" tabIndex={-1}
              aria-selected={candidate.value === value} data-active={active === start + index} data-candidate-index={start + index}
              className={styles.option} disabled={saving} title={candidate.value}
              onMouseDown={event => event.preventDefault()} onClick={() => void choose(candidate.value)}>
              <span>{candidate.label}</span>{candidate.isProject && <span className={styles.source}>当前工程</span>}
            </button>)}
          </div>;
        })}
        {!loading && !error && !candidates.length && <p className={styles.empty}>没有匹配的内容，当前引用保持不变。</p>}
        {!loading && groups.length > 1 && <div className={styles.scrollTail} aria-hidden="true" />}
      </div>
      <nav className={styles.bookmarks} aria-label="下方分类书签">{!loading && bookmarks(false)}</nav>
      <div className={styles.footer}>
        <button type="button" className={styles.tool} disabled={saving || (nullable ? value === null : value === '')}
          title={nullable ? '将引用设为空值' : '将引用设为空字符串'} onClick={() => void choose(nullable ? null : '')}>清除引用值</button>
        <span role="status">{saving ? '正在保存引用…' : '仅明确选择时写入'}</span>
        <button type="button" className={styles.tool} onClick={() => close()}>取消</button>
      </div>
    </div>, document.body)}
  </div>;
}
