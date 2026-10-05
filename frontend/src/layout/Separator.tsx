import { useEffect, useRef, useState } from 'react';
import { clamp } from './geometry';
import { keyboardValue, SeparatorDrag, type Direction, type Orientation } from './interaction';
import styles from './layout.module.css';

export interface SeparatorProps {
  orientation: Orientation;
  value: number;
  min: number;
  max: number;
  onChange(value: number): void;
  onReset(): void;
  label: string;
  direction?: Direction;
  step?: number;
  disabled?: boolean;
}

export function Separator({ orientation, value, min, max, onChange, onReset, label,
  direction = 1, step = 10, disabled = false }: SeparatorProps) {
  const drag = useRef(new SeparatorDrag());
  const [dragging, setDragging] = useState(false);
  const bounds = { min, max: Math.max(min, max) };
  const current = clamp(value, bounds);
  const unavailable = disabled || max <= min;
  const coordinate = (event: { clientX: number; clientY: number }) => orientation === 'vertical' ? event.clientX : event.clientY;

  useEffect(() => {
    const gesture = drag.current;
    const stop = () => { gesture.end(); setDragging(false); };
    window.addEventListener('blur', stop);
    return () => { window.removeEventListener('blur', stop); gesture.end(); };
  }, []);
  useEffect(() => {
    drag.current.end(); setDragging(false);
  }, [unavailable, orientation, direction]);

  const finish = (pointerId: number) => { if (drag.current.end(pointerId)) setDragging(false); };
  return <div className={styles.separator} role="separator" tabIndex={0}
    aria-label={label} aria-orientation={orientation} aria-valuemin={min} aria-valuemax={bounds.max}
    aria-valuenow={current} aria-disabled={unavailable} data-dragging={dragging}
    title={`${label}：拖动或方向键调整，Home/End 到边界；双击仅恢复此分隔线。`}
    onPointerDown={event => {
      if (unavailable || event.button !== 0 || !event.isPrimary) return;
      event.preventDefault(); event.currentTarget.focus();
      if (drag.current.begin(event.pointerId, coordinate(event), current, event.currentTarget)) setDragging(true);
    }}
    onPointerMove={event => {
      if (unavailable) return;
      const next = drag.current.move(event.pointerId, coordinate(event), bounds, direction);
      if (next !== null && next !== current) onChange(next);
    }}
    onPointerUp={event => finish(event.pointerId)} onPointerCancel={event => finish(event.pointerId)}
    onLostPointerCapture={event => finish(event.pointerId)}
    onDoubleClick={event => { event.preventDefault(); drag.current.end(); setDragging(false); onReset(); }}
    onKeyDown={event => {
      if (unavailable || event.altKey || event.ctrlKey || event.metaKey) return;
      const next = keyboardValue(event.key, orientation, current, bounds, direction, step);
      if (next !== null) { event.preventDefault(); if (next !== current) onChange(next); }
    }} />;
}
