import type { WorkbenchLayout } from '../preferences/types';

export interface Bounds { min: number; max: number }
export const LAYOUT = { left: 218, right: 370, compactLeft: 190, compactRight: 340,
  compactAt: 1200, minLeft: 160, minRight: 305, editor: 380, narrowEditor: 120, separator: 6 } as const;

export function clamp(value: number, { min, max }: Bounds): number {
  return Math.min(Math.max(min, max), Math.max(min, Number.isFinite(value) ? value : min));
}

export function resolveLayout(width: number, layout: WorkbenchLayout) {
  width = Number.isFinite(width) ? Math.max(0, width) : 0;
  const count = Number(layout.filesVisible) + Number(layout.previewVisible);
  const separator = count ? Math.min(LAYOUT.separator, width / count) : 0;
  const available = Math.max(0, width - count * separator);
  const minLeft = layout.filesVisible ? LAYOUT.minLeft : 0;
  const minRight = layout.previewVisible ? LAYOUT.minRight : 0;
  const minimum = minLeft + minRight;
  const editorMinimum = Math.min(available, Math.max(LAYOUT.narrowEditor, Math.min(LAYOUT.editor, available - minimum)));
  const budget = available - editorMinimum;
  const scale = minimum ? Math.min(1, budget / minimum) : 1;
  const lowLeft = minLeft * scale, lowRight = minRight * scale;
  const compact = width <= LAYOUT.compactAt;
  let left = layout.filesVisible ? Math.max(lowLeft, layout.leftWidth ?? (compact ? LAYOUT.compactLeft : LAYOUT.left)) : 0;
  let right = layout.previewVisible ? Math.max(lowRight, layout.rightWidth ?? (compact ? LAYOUT.compactRight : LAYOUT.right)) : 0;
  if (left + right > budget) {
    const excess = left + right - lowLeft - lowRight;
    const fraction = excess ? Math.max(0, budget - lowLeft - lowRight) / excess : 0;
    left = lowLeft + (left - lowLeft) * fraction;
    right = lowRight + (right - lowRight) * fraction;
  }
  return { left, right, editor: Math.max(0, available - left - right), separator,
    resizable: available >= minimum + LAYOUT.editor,
    leftBounds: { min: minLeft, max: Math.max(minLeft, Math.min(10000, available - right - LAYOUT.editor)) },
    rightBounds: { min: minRight, max: Math.max(minRight, Math.min(10000, available - left - LAYOUT.editor)) } };
}

export function resetWidth(layout: WorkbenchLayout, side: 'left' | 'right'): WorkbenchLayout {
  return { ...layout, [side === 'left' ? 'leftWidth' : 'rightWidth']: null };
}

export function resizeWidth(layout: WorkbenchLayout, side: 'left' | 'right', value: number, width: number): WorkbenchLayout {
  const measured = resolveLayout(width, layout);
  if (!measured.resizable || !(side === 'left' ? layout.filesVisible : layout.previewVisible)) return layout;
  const bounds = side === 'left' ? measured.leftBounds : measured.rightBounds;
  return { ...layout, [side === 'left' ? 'leftWidth' : 'rightWidth']: clamp(value, bounds) };
}
