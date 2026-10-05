import { clamp, type Bounds } from './geometry';

export type Orientation = 'vertical' | 'horizontal';
export type Direction = 1 | -1;

export function keyboardValue(key: string, orientation: Orientation, value: number, bounds: Bounds,
  direction: Direction = 1, step = 10): number | null {
  if (key === 'Home') return bounds.min;
  if (key === 'End') return bounds.max;
  const negative = orientation === 'vertical' ? 'ArrowLeft' : 'ArrowUp';
  const positive = orientation === 'vertical' ? 'ArrowRight' : 'ArrowDown';
  if (key !== negative && key !== positive) return null;
  return clamp(value + (key === positive ? 1 : -1) * direction * step, bounds);
}

interface CaptureTarget {
  setPointerCapture(pointerId: number): void;
  hasPointerCapture(pointerId: number): boolean;
  releasePointerCapture(pointerId: number): void;
}

/** Owns the transient pointer gesture only; the caller owns its view value. */
export class SeparatorDrag {
  private active: { id: number; coordinate: number; value: number; target: CaptureTarget } | null = null;

  begin(id: number, coordinate: number, value: number, target: CaptureTarget): boolean {
    if (this.active) return false;
    try { target.setPointerCapture(id); } catch { return false; }
    this.active = { id, coordinate, value, target };
    return true;
  }

  move(id: number, coordinate: number, bounds: Bounds, direction: Direction = 1): number | null {
    if (!this.active || this.active.id !== id) return null;
    return clamp(this.active.value + (coordinate - this.active.coordinate) * direction, bounds);
  }

  end(id?: number): boolean {
    const active = this.active;
    if (!active || id !== undefined && active.id !== id) return false;
    this.active = null;
    // Clear ownership before release: lostpointercapture can fire immediately.
    try { if (active.target.hasPointerCapture(active.id)) active.target.releasePointerCapture(active.id); } catch { /* Detached target already released capture. */ }
    return true;
  }
}
