import { describe, expect, it } from 'vitest';
import type { WorkbenchLayout } from '../preferences/types';
import { resolveLayout, resetWidth, resizeWidth } from './geometry';

const initial: WorkbenchLayout = { leftWidth: null, rightWidth: null, previewRatio: .62, filesVisible: true, previewVisible: true };

describe('三栏实际可用宽度', () => {
  it('默认栏宽与6px分隔热区一起计入容器，中心保留目标宽度', () => {
    const wide = resolveLayout(1400, initial);
    expect([wide.left, wide.right, wide.editor, wide.separator]).toEqual([218, 370, 800, 6]);
    expect(wide.leftBounds).toEqual({ min: 160, max: 638 });
    expect(wide.rightBounds).toEqual({ min: 305, max: 790 });
    expect(wide.resizable).toBe(true);
    expect(resolveLayout(1024, initial).editor).toBe(482);
  });
  it('隐藏侧栏不占宽，已有覆盖值在恢复可见时继续参与布局', () => {
    const layout = { ...initial, leftWidth: 260, rightWidth: 390, filesVisible: false };
    expect(resolveLayout(1000, layout)).toMatchObject({ left: 0, right: 390, editor: 604, separator: 6 });
    expect(resolveLayout(1000, { ...layout, previewVisible: false })).toMatchObject({ left: 0, right: 0, editor: 1000 });
    expect(resolveLayout(1400, { ...layout, filesVisible: true })).toMatchObject({ left: 260, right: 390 });
  });
  it('拖动只改指定宽度，边界始终保留另侧与中心，双击只重置该覆盖值', () => {
    const layout = { ...initial, leftWidth: 218, rightWidth: 370 };
    expect(resizeWidth(layout, 'left', 9999, 1400)).toEqual({ ...layout, leftWidth: 638 });
    expect(resizeWidth(layout, 'right', 0, 1400)).toEqual({ ...layout, rightWidth: 305 });
    expect(resetWidth(layout, 'left')).toEqual({ ...layout, leftWidth: null });
    expect(resetWidth({ ...layout, filesVisible: false }, 'right')).toEqual({ ...layout, filesVisible: false, rightWidth: null });
  });
  it('极窄窗口压缩显示而不提交后端不接受的宽度，最窄也不溢出', () => {
    for (const width of [0, 1, 10, 120, 300, 500, 700, 856]) {
      const measured = resolveLayout(width, initial);
      expect(measured.left + measured.right + measured.editor + measured.separator * 2).toBeCloseTo(width);
      expect(Math.min(measured.left, measured.right, measured.editor, measured.separator)).toBeGreaterThanOrEqual(0);
      expect(measured.resizable).toBe(false);
      expect(resizeWidth(initial, 'left', 90, width)).toBe(initial);
      expect(measured.leftBounds.max).toBeGreaterThanOrEqual(measured.leftBounds.min);
      expect(measured.rightBounds.max).toBeGreaterThanOrEqual(measured.rightBounds.min);
    }
    expect(resolveLayout(700, initial)).toMatchObject({ left: 160, right: 305, editor: 223 });
    expect(resolveLayout(857, initial)).toMatchObject({ left: 160, right: 305, editor: 380, resizable: true });
    expect(resolveLayout(500, { ...initial, previewVisible: false }).resizable).toBe(false);
    expect(resolveLayout(546, { ...initial, previewVisible: false }).resizable).toBe(true);
  });
  it('未测得容器宽度时不产生NaN或落盘更改', () => {
    expect(resolveLayout(Number.NaN, initial)).toMatchObject({ left: 0, right: 0, editor: 0, resizable: false });
  });
  it('已有超宽覆盖值和所有显隐组合在缩放后仍装入实际容器', () => {
    for (const width of [1, 12, 400, 700, 857, 1024, 1400, 2400]) {
      for (const filesVisible of [false, true]) for (const previewVisible of [false, true]) {
        const layout = { ...initial, filesVisible, previewVisible, leftWidth: 2400, rightWidth: 5000 };
        const measured = resolveLayout(width, layout);
        const count = Number(filesVisible) + Number(previewVisible);
        expect(measured.left + measured.right + measured.editor + measured.separator * count).toBeCloseTo(width);
        if (measured.resizable) {
          expect(measured.editor).toBeGreaterThanOrEqual(380 - 1e-8);
          if (filesVisible) expect(resizeWidth(layout, 'left', -100, width).leftWidth).toBe(160);
          if (previewVisible) expect(resizeWidth(layout, 'right', -100, width).rightWidth).toBe(305);
        }
      }
    }
  });
});
