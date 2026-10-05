import { describe, expect, it, vi } from 'vitest';
import { createWeaponController } from './controller';

describe('武器结构动作生命周期', () => {
  it('重复动作只发送一次，失败保留错误并允许重试', async () => {
    let fail!: (error: Error) => void;
    const action = vi.fn(() => new Promise<void>((_resolve, reject) => { fail = reject; }));
    const controller = createWeaponController(); controller.start('甲', action);
    const first = controller.run('weapon_add', { name: 'gun' });
    expect(await controller.run('weapon_add', { name: 'gun' })).toBe(false);
    expect(action).toHaveBeenCalledTimes(1);
    fail(new Error('引用已失效')); expect(await first).toBe(false);
    expect(controller.getSnapshot().error).toBe('引用已失效');
    action.mockResolvedValueOnce(); expect(await controller.run('weapon_add', { name: 'gun' })).toBe(true);
    expect(controller.getSnapshot().error).toBe('');
  });

  it('切页或卸载使旧结果失效，迟到成功不能清空新创建草稿', async () => {
    let finish!: () => void;
    const action = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
    const controller = createWeaponController(); controller.start('甲', action);
    const first = controller.run('weapon_expand', {});
    controller.start('乙', vi.fn(async () => {})); finish(); expect(await first).toBe(false);
    expect(controller.getSnapshot().identity).toBe('乙');
    expect(controller.getSnapshot().error).toBe('');
    controller.stop(); expect(await controller.run('weapon_add', {})).toBe(false);
  });

  it('卸载后迟到失败不通知旧订阅，也不污染再次启动的错误状态', async () => {
    let fail!: (reason: Error) => void;
    const controller = createWeaponController();
    controller.start('旧页', () => new Promise<void>((_resolve, reject) => { fail = reject; }));
    const listener = vi.fn(); controller.subscribe(listener);
    const pending = controller.run('weapon_add_override', {});
    controller.stop(); const before = listener.mock.calls.length;
    fail(new Error('旧请求失败')); expect(await pending).toBe(false);
    expect(listener).toHaveBeenCalledTimes(before);
    controller.start('新页', async () => {});
    expect(controller.getSnapshot().error).toBe('');
  });
});
