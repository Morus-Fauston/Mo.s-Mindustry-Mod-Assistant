import type { PreviewScene } from './types';

export interface Point { x: number; y: number }
export interface Size { width: number; height: number }
export interface Bounds extends Point, Size {}
/** Translation uses CSS pixels; scene pixels are independent of display DPR. */
export interface Viewport extends Point { scale: number }
export const MIN_SCALE = 1 / 256;
export const MAX_SCALE = 64;

const clampScale = (scale: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));

export function sceneBounds(scene: PreviewScene | null): Bounds {
  if (!scene) return { x: 0, y: 0, width: 0, height: 0 };
  let left = 0; let top = 0;
  let right = Math.max(0, scene.width); let bottom = Math.max(0, scene.height);
  for (const layer of scene.layers) {
    left = Math.min(left, layer.x); top = Math.min(top, layer.y);
    right = Math.max(right, layer.x + layer.width); bottom = Math.max(bottom, layer.y + layer.height);
  }
  for (const circle of scene.circles) {
    left = Math.min(left, circle.cx - circle.radius); top = Math.min(top, circle.cy - circle.radius);
    right = Math.max(right, circle.cx + circle.radius); bottom = Math.max(bottom, circle.cy + circle.radius);
  }
  return { x: left, y: top, width: right - left, height: bottom - top };
}

export function fitViewport(bounds: Bounds, size: Size, padding = 24): Viewport {
  const scale = bounds.width > 0 && bounds.height > 0
    ? clampScale(Math.min(Math.max(1, size.width - padding * 2) / bounds.width,
      Math.max(1, size.height - padding * 2) / bounds.height)) : 1;
  return { scale, x: size.width / 2 - (bounds.x + bounds.width / 2) * scale,
    y: size.height / 2 - (bounds.y + bounds.height / 2) * scale };
}

export function screenToScene(viewport: Viewport, point: Point): Point {
  return { x: (point.x - viewport.x) / viewport.scale, y: (point.y - viewport.y) / viewport.scale };
}

export function sceneToScreen(viewport: Viewport, point: Point): Point {
  return { x: point.x * viewport.scale + viewport.x, y: point.y * viewport.scale + viewport.y };
}

export function zoomAt(viewport: Viewport, anchor: Point, factor: number): Viewport {
  if (!Number.isFinite(factor) || factor <= 0) return viewport;
  const point = screenToScene(viewport, anchor);
  const scale = clampScale(viewport.scale * factor);
  return { scale, x: anchor.x - point.x * scale, y: anchor.y - point.y * scale };
}

export function panBy(viewport: Viewport, delta: Point): Viewport {
  return { ...viewport, x: viewport.x + delta.x, y: viewport.y + delta.y };
}

export function canvasBackingSize(size: Size, dpr: number): Size {
  const ratio = Number.isFinite(dpr) && dpr > 0 ? dpr : 1;
  return { width: Math.max(1, Math.round(size.width * ratio)), height: Math.max(1, Math.round(size.height * ratio)) };
}
