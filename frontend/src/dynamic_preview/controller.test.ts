import { describe, expect, it } from 'vitest';
import { DynamicPreviewController, type AnimationClock } from './controller';
import type { DynamicPreviewDescriptor, DynamicPreviewState } from './types';

export const descriptor: DynamicPreviewDescriptor = {
  supported: true, notices: [], recoilTime: 10, cooldownTime: 20,
  teams: [{ value: '默认', label: '默认', color: '#ffc832' }, { value: '蓝队', label: '蓝队', color: '#50a9ee' }],
  healthLevels: [{ value: '满血', label: '满血', fraction: 1 }, { value: '残血', label: '残血', fraction: 0.15 }],
  directions: [{ value: '上', label: '上', degrees: 0 }, { value: '右', label: '右', degrees: 90 }],
  weapons: [], engine: null, teamLayerKeys: [], cellLayerKeys: [], heat: null, treads: null,
  flash: { radius: 3, color: '#fff3a1', z: 20 }, colorize: 'qt-colorize-strength-1',
};
class Clock implements AnimationClock {
  time = 0;
  next = 0;
  callbacks = new Map<number, (time: number) => void>();
  now = () => this.time;
  request = (callback: (time: number) => void) => { const id = ++this.next; this.callbacks.set(id, callback); return id; };
  cancel = (id: number) => { this.callbacks.delete(id); };
  frame(time: number) {
    this.time = time;
    const callbacks = [...this.callbacks.values()]; this.callbacks.clear();
    callbacks.forEach(callback => callback(time));
  }
}

describe('可注入预览时钟', () => {
  it('暂停后开火停在开火帧，单步只推进一个tick且不受2倍速影响', () => {
    const clock = new Clock(), changes: DynamicPreviewState[] = [];
    const controller = new DynamicPreviewController(clock, state => changes.push(state));
    controller.setScene('session:path', descriptor);
    controller.dispatch({ type: 'start' });
    controller.dispatch({ type: 'speed', value: 2 });
    clock.frame(50);
    expect(controller.snapshot().animation.timeTick).toBe(6);
    controller.dispatch({ type: 'togglePause' });
    expect(clock.callbacks.size).toBe(0);
    controller.dispatch({ type: 'fire' });
    expect(controller.snapshot().animation.muzzleFlashTicks).toBe(3);
    const paused = controller.snapshot();
    clock.frame(10000);
    expect(controller.snapshot()).toBe(paused);
    controller.dispatch({ type: 'step' });
    expect(controller.snapshot().animation.timeTick).toBe(7);
    expect(controller.snapshot().animation.muzzleFlashTicks).toBe(2);
    expect(controller.snapshot().paused).toBe(true);
    expect(clock.callbacks.size).toBe(0);
    controller.dispatch({ type: 'togglePause' });
    clock.frame(10025);
    expect(controller.snapshot().animation.timeTick).toBe(10);
    expect(changes.length).toBeGreaterThan(3);
  });
  it('隐藏取消时钟，恢复不追补，取消后晚到回调和重复回调不重启循环', () => {
    const clock = new Clock(), controller = new DynamicPreviewController(clock, () => {});
    controller.setScene('s:a', descriptor); controller.dispatch({ type: 'start' });
    const oldCallback = [...clock.callbacks.values()][0];
    clock.frame(25);
    expect(controller.snapshot().animation.timeTick).toBe(1.5);
    oldCallback(50);
    expect(clock.callbacks.size).toBe(1);
    expect(controller.snapshot().animation.timeTick).toBe(1.5);
    const cancelled = [...clock.callbacks.values()][0];
    controller.setVisible(false);
    expect(clock.callbacks.size).toBe(0);
    clock.frame(60000); cancelled(60000);
    expect(clock.callbacks.size).toBe(0);
    expect(controller.snapshot().animation.timeTick).toBe(1.5);
    controller.setVisible(true); controller.setVisible(true);
    expect(clock.callbacks.size).toBe(1);
    clock.frame(60025);
    expect(controller.snapshot().animation.timeTick).toBe(3);
  });
  it('同一内容刷新保状态，临时无可用场景停钟，切内容和会话复位且隔离旧回调', () => {
    const clock = new Clock(), controller = new DynamicPreviewController(clock, () => {});
    controller.setScene('s:a', descriptor); controller.dispatch({ type: 'start' });
    controller.dispatch({ type: 'team', value: '蓝队' });
    clock.frame(25);
    const stale = [...clock.callbacks.values()][0];
    controller.setScene('s:a', { ...descriptor });
    expect(controller.snapshot().team).toBe('蓝队');
    expect(controller.snapshot().animation.timeTick).toBe(1.5);
    controller.setScene('s:a', null);
    expect(clock.callbacks.size).toBe(0);
    clock.frame(1000); stale(1000);
    controller.setScene('s:a', descriptor); clock.frame(1025);
    expect(controller.snapshot().animation.timeTick).toBe(3);
    controller.setScene('s:b', descriptor);
    expect(controller.snapshot().enabled).toBe(false);
    expect(controller.snapshot().team).toBe('默认');
    expect(controller.snapshot().animation.timeTick).toBe(0);
    controller.dispatch({ type: 'start' });
    controller.setScene('new-session:b', descriptor);
    expect(controller.snapshot().enabled).toBe(false);
    expect(clock.callbacks.size).toBe(0);
    controller.setScene(null, null);
    expect(controller.snapshot().team).toBe('');
  });
  it('结束后开始保时间，复位恢复全部默认选项，运行中单步不越权', () => {
    const clock = new Clock(), controller = new DynamicPreviewController(clock, () => {});
    controller.setScene('s:a', descriptor); controller.dispatch({ type: 'start' });
    controller.dispatch({ type: 'speed', value: 2 });
    controller.dispatch({ type: 'moving', value: true });
    controller.dispatch({ type: 'direction', value: '右' });
    controller.dispatch({ type: 'team', value: '蓝队' });
    controller.dispatch({ type: 'health', value: '残血' });
    controller.dispatch({ type: 'fire' }); clock.frame(50);
    const running = controller.snapshot();
    controller.dispatch({ type: 'step' });
    expect(controller.snapshot()).toBe(running);
    controller.dispatch({ type: 'stop' }); clock.frame(5000);
    expect(controller.snapshot().animation).toEqual(running.animation);
    controller.dispatch({ type: 'start' }); clock.frame(5025);
    expect(controller.snapshot().animation.timeTick).toBe(9);
    controller.dispatch({ type: 'reset' });
    expect(controller.snapshot()).toEqual({ enabled: false, paused: false, speed: 1, moving: false,
      direction: '上', team: '默认', health: '满血', animation: { timeTick: 0, recoil: 0, heat: 0, muzzleFlashTicks: 0, treadTime: 0 } });
    expect(clock.callbacks.size).toBe(0);
  });
  it('释放幂等、晚到回调不能发帧，监听器在帧内释放也不会重排RAF', () => {
    const clock = new Clock(); let frames = 0;
    const controller = new DynamicPreviewController(clock, () => { frames++; });
    controller.setScene('s:a', descriptor); controller.dispatch({ type: 'start' });
    const stale = [...clock.callbacks.values()][0], before = frames;
    controller.dispose(); controller.dispose(); stale(16);
    controller.setScene('s:b', descriptor); controller.dispatch({ type: 'start' }); controller.setVisible(true);
    expect(frames).toBe(before); expect(clock.callbacks.size).toBe(0);
    const other = new DynamicPreviewController(clock, state => { if (state.animation.timeTick > 0) other.dispose(); });
    other.setScene('s:a', descriptor); other.dispatch({ type: 'start' }); clock.frame(16);
    expect(clock.callbacks.size).toBe(0);
  });
  it('无场景或不支持的场景不启动，非法选择不会污染后端选项', () => {
    const clock = new Clock(), controller = new DynamicPreviewController(clock, () => {});
    controller.dispatch({ type: 'start' }); expect(clock.callbacks.size).toBe(0);
    controller.setScene('s:a', { ...descriptor, supported: false });
    controller.dispatch({ type: 'start' }); expect(clock.callbacks.size).toBe(0);
    controller.setScene('s:a', descriptor);
    const before = controller.snapshot();
    controller.dispatch({ type: 'team', value: '任意伪造队伍' });
    controller.dispatch({ type: 'speed', value: 3 as 2 });
    expect(controller.snapshot()).toBe(before);
    expect(Object.isFrozen(before)).toBe(true); expect(Object.isFrozen(before.animation)).toBe(true);
  });
  it.each([0.5, 1, 2] as const)('真实clock seam在不同刷新率和%s倍速下保持同一elapsed结果', speed => {
    for (const fps of [30, 60, 120]) {
      const clock = new Clock(), controller = new DynamicPreviewController(clock, () => {});
      controller.setScene('s:a', descriptor); controller.dispatch({ type: 'start' });
      controller.dispatch({ type: 'speed', value: speed });
      for (let index = 1; index <= fps; index++) clock.frame(index * 1000 / fps);
      expect(controller.snapshot().animation.timeTick).toBeCloseTo(60 * speed, 10);
      controller.dispose(); expect(clock.callbacks.size).toBe(0);
    }
  });
});
