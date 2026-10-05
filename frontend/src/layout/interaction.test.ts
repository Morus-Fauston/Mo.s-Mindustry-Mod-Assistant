import { describe, expect, it, vi } from 'vitest';
import { keyboardValue, SeparatorDrag } from './interaction';

describe('分隔线鼠标与键盘一致边界', () => {
  it('右分隔线的右箭头减小右栏，水平线仅接受上下键并支持Home/End', () => {
    const bounds = { min: 160, max: 400 };
    expect(keyboardValue('ArrowRight', 'vertical', 390, bounds, -1)).toBe(380);
    expect(keyboardValue('ArrowLeft', 'vertical', 390, bounds, -1)).toBe(400);
    expect(keyboardValue('ArrowDown', 'horizontal', 395, bounds)).toBe(400);
    expect(keyboardValue('ArrowUp', 'horizontal', 165, bounds)).toBe(160);
    expect(keyboardValue('Home', 'vertical', 300, bounds)).toBe(160);
    expect(keyboardValue('End', 'horizontal', 300, bounds)).toBe(400);
    expect(keyboardValue('ArrowLeft', 'horizontal', 300, bounds)).toBeNull();
    expect(keyboardValue('a', 'vertical', 300, bounds)).toBeNull();
  });
  it('捕获唯一指针、限制边界，并在结束和取消释放，后续移动不再修改', () => {
    const target = { setPointerCapture: vi.fn(), releasePointerCapture: vi.fn(), hasPointerCapture: () => true };
    const drag = new SeparatorDrag();
    expect(drag.begin(5, 100, 370, target)).toBe(true);
    expect(drag.begin(6, 100, 370, target)).toBe(false);
    expect(drag.move(6, 200, { min: 305, max: 600 }, -1)).toBeNull();
    expect(drag.move(5, 200, { min: 305, max: 600 }, -1)).toBe(305);
    expect(drag.move(5, -300, { min: 305, max: 600 }, -1)).toBe(600);
    expect(drag.end(6)).toBe(false);
    expect(drag.end(5)).toBe(true);
    expect(target.releasePointerCapture).toHaveBeenCalledWith(5);
    expect(drag.move(5, 120, { min: 305, max: 600 })).toBeNull();
    expect(drag.begin(7, 0, 200, target)).toBe(true);
    expect(drag.end()).toBe(true);
    expect(target.releasePointerCapture).toHaveBeenLastCalledWith(7);
  });
  it('浏览器拒绝捕获时不进入拖动，目标销毁时清理不留下活跃指针', () => {
    const drag = new SeparatorDrag();
    const blocked = { setPointerCapture: () => { throw new Error('not active'); }, hasPointerCapture: () => false,
      releasePointerCapture: vi.fn() };
    expect(drag.begin(1, 10, 200, blocked)).toBe(false);
    expect(drag.move(1, 20, { min: 160, max: 300 })).toBeNull();
    const detached = { setPointerCapture: vi.fn(), hasPointerCapture: () => true,
      releasePointerCapture: () => { throw new Error('detached'); } };
    expect(drag.begin(2, 10, 200, detached)).toBe(true);
    expect(drag.end()).toBe(true);
    expect(drag.end()).toBe(false);
    expect(drag.move(2, 100, { min: 160, max: 300 })).toBeNull();
  });
  it('窗口改变后的新边界立即作用于鼠标，和键盘落在相同端点', () => {
    const drag = new SeparatorDrag();
    const target = { setPointerCapture: vi.fn(), releasePointerCapture: vi.fn(), hasPointerCapture: () => false };
    drag.begin(1, 0, 230, target);
    const bounds = { min: 160, max: 240 };
    expect(drag.move(1, 100, bounds)).toBe(keyboardValue('End', 'vertical', 230, bounds));
    expect(drag.move(1, -100, bounds)).toBe(keyboardValue('Home', 'vertical', 230, bounds));
    drag.end();
    expect(target.releasePointerCapture).not.toHaveBeenCalled();
  });
});
