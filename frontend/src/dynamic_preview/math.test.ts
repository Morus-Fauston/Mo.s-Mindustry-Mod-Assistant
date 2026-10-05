import { describe, expect, it } from 'vitest';
import { advanceAnimation, advanceElapsed, initialAnimation, fireAnimation, pulse, recoilOffset, flashOpacity, treadFrame, cellColor } from './math';

describe('动态预览的 Python 固定向量', () => {
  it('开火与推进不修改调用方状态，衰减及颜色符合 core 第 1、3、6 tick', () => {
    const initial = Object.freeze(initialAnimation());
    let state = fireAnimation(initial);
    expect(initial.recoil).toBe(0);
    expect(cellColor('#50a9ee', 0.15, 0)).toBe('#2e6189');
    for (const [delta, time, recoil, heat, opacity, offset, expectedPulse, color] of [
      [1, 1, 0.9, 0.95, 2 / 3, -1.6544990139122189, 0.6237019796272615, '#3e84b9'],
      [2, 3, 0.7, 0.85, 0, -1.0524621053100636, 0.840819380011667, '#50a9ee'],
      [10, 6, 0.4, 0.7, 0, -0.3843598188740579, 0.9987474933020273, '#336b97'],
    ] as const) {
      state = advanceAnimation(Object.freeze(state), delta, { recoilTime: 10, cooldownTime: 20, moving: true });
      expect(state.timeTick).toBe(time);
      expect(state.recoil).toBeCloseTo(recoil, 12);
      expect(state.heat).toBeCloseTo(heat, 12);
      expect(flashOpacity(state)).toBeCloseTo(opacity, 12);
      expect(recoilOffset(state, 2)).toBeCloseTo(offset, 12);
      expect(pulse(state.timeTick)).toBeCloseTo(expectedPulse, 12);
      expect(cellColor('#50a9ee', 0.15, state.timeTick)).toBe(color);
    }
    expect(treadFrame(state, 3)).toBe(0);
  });
  it('半偶数颜色、原地和无效时间边界保持 Python 语义', () => {
    expect(cellColor('#010305', 0, 0)).toBe('#000202');
    expect(cellColor('#50a9ee', 1, 100)).toBe('#50a9ee');
    const state = fireAnimation(initialAnimation());
    const timing = { recoilTime: 10, cooldownTime: 20, moving: false };
    for (const delta of [0, -3, NaN, Infinity]) expect(advanceAnimation(state, delta, timing)).toEqual(state);
    expect(advanceAnimation(state, 2, timing).treadTime).toBe(0);
    expect(treadFrame(state, 0)).toBe(0);
  });
  it.each([0.5, 1, 2] as const)('30/60/120 fps 在 %sx 的一秒内推进同一模拟时间', speed => {
    for (const fps of [30, 60, 120]) {
      let state = fireAnimation(initialAnimation());
      for (let frame = 0; frame < fps; frame++) state = advanceElapsed(state, 1000 / fps, speed, { recoilTime: 100, cooldownTime: 200, moving: true });
      expect(state.timeTick).toBeCloseTo(60 * speed, 10);
      expect(state.treadTime).toBeCloseTo(60 * speed, 10);
      expect(state.recoil).toBeCloseTo(Math.max(0, 1 - 0.6 * speed), 10);
    }
  });
  it('单帧停顿只追补100ms墙钟，2倍速仍分为合法子步', () => {
    const state = advanceElapsed(fireAnimation(initialAnimation()), 5000, 2, { recoilTime: 100, cooldownTime: 200, moving: true });
    expect(state.timeTick).toBe(12);
    expect(state.recoil).toBeCloseTo(0.88, 12);
  });
});
