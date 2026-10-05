import { describe, expect, it } from 'vitest';
import { fitViewport, sceneBounds, screenToScene, sceneToScreen, zoomAt, panBy, canvasBackingSize } from './viewport';
import type { PreviewScene } from './types';

describe('预览视口数学', () => {
  it('适应完整图层范围，包含主体外侧的武器和引擎圆', () => {
    const scene: PreviewScene = { sessionId: 'a', width: 100, height: 80, status: 'ready', warnings: [],
      layers: [{ key: 'weapon', resourceId: 'r', x: -20, y: 20, width: 30, height: 40, z: 1, flipX: true, tooltip: '' }],
      circles: [{ key: 'engine', cx: 110, cy: 40, radius: 10, z: 0, color: '#ffffff', tooltip: '' }],
    };
    expect(sceneBounds(scene)).toEqual({ x: -20, y: 0, width: 140, height: 80 });
    expect(fitViewport(sceneBounds(scene), { width: 328, height: 208 })).toEqual({ scale: 2, x: 64, y: 24 });
  });
  it('鼠标锚点缩放后场景点不漂移，平移只改变CSS像素偏移', () => {
    const initial = { scale: 2, x: 30, y: 50 };
    const anchor = { x: 90, y: 110 };
    expect(screenToScene(initial, anchor)).toEqual({ x: 30, y: 30 });
    const zoomed = zoomAt(initial, anchor, 2);
    expect(zoomed).toEqual({ scale: 4, x: -30, y: -10 });
    expect(sceneToScreen(zoomed, { x: 30, y: 30 })).toEqual(anchor);
    expect(panBy(zoomed, { x: 15, y: -20 })).toEqual({ scale: 4, x: -15, y: -30 });
    expect(initial).toEqual({ scale: 2, x: 30, y: 50 });
  });
  it('高DPI只改变backing尺寸，不改变场景与CSS坐标', () => {
    for (const [dpr, width, height] of [[1, 301, 199], [1.25, 376, 249], [1.5, 452, 299], [2, 602, 398]]) {
      expect(canvasBackingSize({ width: 301, height: 199 }, dpr)).toEqual({ width, height });
      expect(sceneToScreen({ scale: 2, x: 50, y: 40 }, { x: 10, y: -5 })).toEqual({ x: 70, y: 30 });
    }
  });
  it('极端滚轮输入有界，空场景和零尺寸仍得到有限视口', () => {
    const initial = { scale: 1, x: 0, y: 0 };
    expect(zoomAt(initial, { x: 0, y: 0 }, 1e9).scale).toBe(64);
    expect(zoomAt(initial, { x: 0, y: 0 }, 1e-9).scale).toBe(1 / 256);
    expect(zoomAt(initial, { x: 0, y: 0 }, NaN)).toEqual(initial);
    expect(fitViewport(sceneBounds(null), { width: 0, height: 0 })).toEqual(initial);
  });
});
