import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import styles from './BasicForm.module.css';

export interface MenuAction { id: string; label: string; run: () => void }

/** The menu lives above the scrolling form and preserves native keyboard focus. */
export function ActionMenu({ label, children, items, disabled }: {
  label: string; children: React.ReactNode; items: MenuAction[]; disabled: boolean;
}) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const anchor = useRef<{ top: number; left: number } | null>(null);
  const [position, setPosition] = useState<{ left: number; top: number; maxHeight: number } | null>(null);
  const close = (restore = true) => { setPosition(null); if (restore) button.current?.focus(); };
  const open = () => {
    if (disabled || !items.length) return;
    const bounds = button.current!.getBoundingClientRect();
    anchor.current = { top: bounds.top, left: bounds.left };
    const roomBelow = window.innerHeight - bounds.bottom - 12;
    const height = Math.min(280, items.length * 30 + 8);
    const top = roomBelow >= Math.min(height, 120) ? bounds.bottom + 4 : Math.max(8, bounds.top - height - 4);
    setPosition({ left: Math.max(8, Math.min(bounds.left, window.innerWidth - 268)), top,
      maxHeight: Math.max(60, Math.min(height, window.innerHeight - top - 8)) });
  };
  useEffect(() => {
    if (!position) return;
    menu.current?.querySelector<HTMLButtonElement>('button')?.focus({ preventScroll: true });
    const outside = (event: PointerEvent) => {
      if (!menu.current?.contains(event.target as Node) && !button.current?.contains(event.target as Node)) close(false);
    };
    const resize = () => close(false);
    const scroll = (event: Event) => {
      if (menu.current?.contains(event.target as Node)) return;
      // The browser may deliver the trigger's scroll-into-view event after open.
      // Close only when the anchor actually moved, not for that delayed event.
      const bounds = button.current?.getBoundingClientRect();
      if (bounds && anchor.current && (Math.abs(bounds.top - anchor.current.top) > .5 ||
          Math.abs(bounds.left - anchor.current.left) > .5)) close(false);
    };
    document.addEventListener('pointerdown', outside);
    window.addEventListener('resize', resize);
    window.addEventListener('scroll', scroll, true);
    return () => { document.removeEventListener('pointerdown', outside); window.removeEventListener('resize', resize); window.removeEventListener('scroll', scroll, true); };
  }, [position]);
  useEffect(() => { if (disabled) setPosition(null); }, [disabled]);
  return <>
    <button ref={button} type="button" className={styles.iconButton} aria-label={label} title={label}
      aria-haspopup="menu" aria-expanded={Boolean(position)} aria-controls={position ? id : undefined}
      disabled={disabled || !items.length} onClick={() => position ? close() : open()}
      onPointerDown={event => { if (position) event.preventDefault(); }}
      onKeyDown={event => { if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); open(); } }}>{children}</button>
    {position && createPortal(<div ref={menu} id={id} role="menu" aria-label={label} className={styles.menu} style={position}
      onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) close(false); }}
      onKeyDown={event => {
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(); return; }
        const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('button')];
        const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
        let next = current;
        if (event.key === 'ArrowDown') next = (current + 1) % buttons.length;
        else if (event.key === 'ArrowUp') next = (current - 1 + buttons.length) % buttons.length;
        else if (event.key === 'Home') next = 0;
        else if (event.key === 'End') next = buttons.length - 1;
        else return;
        event.preventDefault(); buttons[next]?.focus();
      }}>{items.map(item => <button type="button" role="menuitem" key={item.id} onClick={() => { close(); item.run(); }}>{item.label}</button>)}</div>, document.body)}
  </>;
}
