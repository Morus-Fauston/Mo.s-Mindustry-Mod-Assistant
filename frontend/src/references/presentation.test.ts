import { describe, expect, it } from 'vitest';
import { createLatestRequest, moveCandidateIndex, popupGeometry } from './presentation';

describe('引用弹层请求与边界', () => {
  it('旧搜索迟到不能覆盖新搜索，关闭后成功或失败均被丢弃', async () => {
    const gate = createLatestRequest();
    let finish!: (value: string) => void;
    const first = gate.run(() => new Promise<string>(resolve => { finish = resolve; }));
    expect(await gate.run(async () => '新结果')).toEqual({ current: true, value: '新结果' });
    finish('旧结果'); expect(await first).toEqual({ current: false });
    let fail!: (error: Error) => void;
    const closed = gate.run(() => new Promise<string>((_resolve, reject) => { fail = reject; }));
    gate.invalidate(); fail(new Error('已关闭请求'));
    expect(await closed).toEqual({ current: false });
  });

  it('当前请求失败仍反馈，重开后可正常查询', async () => {
    const gate = createLatestRequest();
    await expect(gate.run(async () => { throw new Error('读取失败'); })).rejects.toThrow('读取失败');
    gate.invalidate();
    expect(await gate.run(async () => [])).toEqual({ current: true, value: [] });
  });

  it('初始无候选选中，上下只移动候选且无结果时保持未选中', () => {
    expect(moveCandidateIndex(-1, 1, 3)).toBe(0);
    expect(moveCandidateIndex(-1, -1, 3)).toBe(2);
    expect(moveCandidateIndex(2, 1, 3)).toBe(2);
    expect(moveCandidateIndex(0, -1, 3)).toBe(0);
    expect(moveCandidateIndex(-1, 1, 0)).toBe(-1);
  });

  it.each([
    [320, 480, { left: 250, top: 380, bottom: 410, width: 100 }],
    [1280, 720, { left: 900, top: 30, bottom: 60, width: 300 }],
    [240, 220, { left: 0, top: 100, bottom: 130, width: 220 }],
  ])('窗口 %s×%s 中弹层不越界', (width, height, anchor) => {
    const box = popupGeometry(anchor, width, height);
    expect(box.left).toBeGreaterThanOrEqual(8);
    expect(box.top).toBeGreaterThanOrEqual(8);
    expect(box.left + box.width).toBeLessThanOrEqual(width - 8);
    expect(box.top + box.height).toBeLessThanOrEqual(height - 8);
  });
});
