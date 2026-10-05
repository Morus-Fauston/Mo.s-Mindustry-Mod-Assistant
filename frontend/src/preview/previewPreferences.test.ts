import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { PreviewPanel } from './PreviewPanel';
import { resolvePreviewSplit } from './PreviewPanel';
import { initialCanvasView, reconcileCanvasView } from './PreviewCanvas';

describe('预览绝对倍率与视图保留', () => {
  const bounds = { x: 0, y: 0, width: 100, height: 50 };
  const size = { width: 500, height: 300 };
  it('默认4代表场景像素绝对四倍，与适应和DPR无关', () => {
    const view = reconcileCanvasView(initialCanvasView(), bounds, size, 4, true);
    expect(view.viewport).toEqual({ x: 50, y: 50, scale: 4 });
    expect(view.appliedZoom).toBe(4);
    expect(reconcileCanvasView(view, { ...bounds, width: 200 }, size, 4, true)).toBe(view);
  });
  it('普通编辑保留用户视口，只有设置值变化才应用绝对值并保留中心场景点', () => {
    const first = reconcileCanvasView(initialCanvasView(), bounds, size, 4, true);
    const manual = { ...first, mode: 'manual' as const, viewport: { x: 80, y: 90, scale: 2 }, checker: false, grid: true };
    expect(reconcileCanvasView(manual, bounds, size, 4, true)).toBe(manual);
    const next = reconcileCanvasView(manual, bounds, size, 8, true);
    expect(next.viewport).toEqual({ x: -430, y: -90, scale: 8 });
    expect(next).toMatchObject({ checker: false, grid: true, mode: 'preset' });
  });
  it('隐藏导致零尺寸时不改变视口，再显示和切页恢复只按实际尺寸差保持中心', () => {
    const saved = { ...reconcileCanvasView(initialCanvasView(), bounds, size, 4, true),
      mode: 'manual' as const, viewport: { x: 80, y: 90, scale: 2 }, checker: false, grid: true };
    expect(reconcileCanvasView(saved, bounds, { width: 1, height: 1 }, 4, true)).toBe(saved);
    expect(reconcileCanvasView(saved, bounds, size, 4, true)).toBe(saved);
    const resized = reconcileCanvasView(saved, bounds, { width: 600, height: 400 }, 4, true);
    expect(resized.viewport).toEqual({ x: 130, y: 140, scale: 2 });
    expect(resized).toMatchObject({ checker: false, grid: true, mode: 'manual' });
  });
  it('主动适应模式才在窗口变化时重新fit，设置变化可切回绝对倍率', () => {
    const fit = { ...reconcileCanvasView(initialCanvasView(), bounds, size, 4, true), mode: 'fit' as const };
    const resized = reconcileCanvasView(fit, bounds, { width: 248, height: 148 }, 4, true);
    expect(resized.viewport).toEqual({ scale: 2, x: 24, y: 24 });
    expect(reconcileCanvasView(resized, bounds, { width: 248, height: 148 }, 1, true).viewport)
      .toEqual({ scale: 1, x: 74, y: 49 });
  });
  it('场景未就绪不消耗设置变化，后续真实场景按设置初始化，非法倍率回退4', () => {
    const initial = initialCanvasView();
    expect(reconcileCanvasView(initial, bounds, size, 8, false)).toBe(initial);
    expect(reconcileCanvasView(initial, bounds, size, 8, true).viewport.scale).toBe(8);
    for (const invalid of [0, 9, 1.5, Number.NaN]) {
      expect(reconcileCanvasView(initial, bounds, size, invalid, true).viewport.scale).toBe(4);
    }
    expect(initialCanvasView()).not.toBe(initial);
  });
});

describe('上下分隔高度', () => {
  it('有限高度为下面资源工具保留空间，默认55%，标题计入边界', () => {
    const value = resolvePreviewSplit(800, null);
    expect(value).toMatchObject({ height: 520, available: 514, min: 230, max: 324, enabled: true });
    expect(value.preview).toBeCloseTo(282.7);
    expect(value.layers).toBeCloseTo(231.3);
    expect(resolvePreviewSplit(800, 0.01).preview).toBe(230);
    expect(resolvePreviewSplit(800, 0.99).preview).toBe(324);
  });
  it('极小父容器使用可滚动面板且禁用拖动，无负高度或不合法比例', () => {
    for (const height of [0, 100, 300, 539, 600]) {
      const split = resolvePreviewSplit(height, .7);
      expect(split.enabled).toBe(false);
      expect(split.preview).toBeGreaterThanOrEqual(201);
      expect(split.layers).toBeGreaterThan(0);
      expect(split.min).toBe(split.max);
      expect(split.preview + split.layers + 6).toBe(split.height);
    }
    expect(resolvePreviewSplit(2000, null).height).toBe(620);
    expect(resolvePreviewSplit(800, Number.NaN)).toEqual(resolvePreviewSplit(800, null));
  });
  it('未选择文档仍保留预览和图层结构，分隔线有独立中文可访问入口，渲染不写比例', () => {
    vi.stubGlobal('window', { devicePixelRatio: 1 });
    try {
      const onPreviewRatioChange = vi.fn();
      const html = renderToStaticMarkup(createElement(PreviewPanel, { document: undefined, previewRatio: .6, onPreviewRatioChange }));
      expect(html).toContain('data-preview-panel="true"');
      expect(html).toContain('aria-label="预览与图层高度"');
      expect(html).toContain('aria-orientation="horizontal"');
      expect(html).toContain('aria-disabled="true"');
      expect(html).toContain('当前内容没有可用图层');
      expect(onPreviewRatioChange).not.toHaveBeenCalled();
    } finally { vi.unstubAllGlobals(); }
  });
});
