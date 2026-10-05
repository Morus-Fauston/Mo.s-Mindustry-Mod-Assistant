import { advanceAnimation, advanceElapsed, fireAnimation, initialAnimation } from './math';
import type { DynamicAction, DynamicPreviewDescriptor, DynamicPreviewState } from './types';

export interface AnimationClock {
  request(callback: (timestampMs: number) => void): number;
  cancel(id: number): void;
  now(): number;
}
export const browserAnimationClock: AnimationClock = {
  request: callback => requestAnimationFrame(callback),
  cancel: id => cancelAnimationFrame(id),
  now: () => performance.now(),
};

export function initialDynamicState(descriptor: DynamicPreviewDescriptor | null = null): DynamicPreviewState {
  return Object.freeze({ enabled: false, paused: false, speed: 1, moving: false,
    direction: descriptor?.directions[0]?.value ?? '', team: descriptor?.teams[0]?.value ?? '',
    health: descriptor?.healthLevels[0]?.value ?? '', animation: Object.freeze(initialAnimation()) });
}

/** A view-only clock. The host supplies session+path identity and actual visibility. */
export class DynamicPreviewController {
  private state = initialDynamicState();
  private identity: string | null = null;
  private descriptor: DynamicPreviewDescriptor | null = null;
  private visible = true;
  private disposed = false;
  private generation = 0;
  private pending: number | null = null;
  private timestamp: number | null = null;

  constructor(private readonly clock: AnimationClock, private readonly onChange: (state: DynamicPreviewState) => void) {}

  snapshot(): DynamicPreviewState { return this.state; }

  setScene(identity: string | null, descriptor: DynamicPreviewDescriptor | null): void {
    if (this.disposed) return;
    this.cancel();
    const changed = identity !== this.identity;
    this.identity = identity;
    this.descriptor = identity ? descriptor : null;
    if (changed) this.state = initialDynamicState(this.descriptor);
    else if (this.descriptor) {
      // Keep time and controls across coordinate/resource refreshes; removed choices use backend defaults.
      const value = (items: { value: string }[], current: string) => items.some(item => item.value === current) ? current : items[0]?.value ?? '';
      this.state = this.freeze({ ...this.state, team: value(this.descriptor.teams, this.state.team),
        health: value(this.descriptor.healthLevels, this.state.health), direction: value(this.descriptor.directions, this.state.direction) });
    }
    this.publish();
    this.startClock();
  }

  setVisible(visible: boolean): void {
    if (this.disposed || this.visible === visible) return;
    this.visible = visible;
    this.cancel();
    this.startClock();
  }

  dispatch(action: DynamicAction): void {
    if (this.disposed) return;
    if (action.type === 'reset') {
      this.cancel(); this.state = initialDynamicState(this.descriptor); this.publish(); return;
    }
    if (!this.identity || !this.descriptor?.supported) return;
    let next = this.state;
    const timing = { ...this.descriptor, moving: next.moving };
    switch (action.type) {
      case 'start': next = { ...next, enabled: true, paused: false }; break;
      case 'stop': next = { ...next, enabled: false, paused: false }; break;
      case 'togglePause': if (next.enabled) next = { ...next, paused: !next.paused }; break;
      case 'fire': if (next.enabled) next = { ...next, animation: fireAnimation(next.animation) }; break;
      case 'step': if (next.enabled && next.paused) next = { ...next, animation: advanceAnimation(next.animation, 1, timing) }; break;
      case 'speed': if ([0.5, 1, 2].includes(action.value)) next = { ...next, speed: action.value }; break;
      case 'moving': if (typeof action.value === 'boolean') next = { ...next, moving: action.value }; break;
      case 'direction': if (this.descriptor.directions.some(item => item.value === action.value)) next = { ...next, direction: action.value }; break;
      case 'team': if (this.descriptor.teams.some(item => item.value === action.value)) next = { ...next, team: action.value }; break;
      case 'health': if (this.descriptor.healthLevels.some(item => item.value === action.value)) next = { ...next, health: action.value }; break;
    }
    if (next === this.state) return;
    this.cancel();
    this.state = this.freeze(next);
    this.publish();
    this.startClock();
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposed = true; this.cancel(); this.descriptor = null; this.identity = null;
  }

  private freeze(state: DynamicPreviewState): DynamicPreviewState {
    return Object.freeze({ ...state, animation: Object.freeze({ ...state.animation }) });
  }
  private publish(): void { if (!this.disposed) this.onChange(this.state); }
  private running(): boolean {
    return !this.disposed && this.visible && this.identity !== null && Boolean(this.descriptor?.supported) && this.state.enabled && !this.state.paused;
  }
  private cancel(): void {
    this.generation++;
    if (this.pending !== null) this.clock.cancel(this.pending);
    this.pending = null; this.timestamp = null;
  }
  private startClock(): void {
    if (!this.running() || this.pending !== null) return;
    this.timestamp = this.clock.now();
    this.schedule();
  }
  private schedule(): void {
    const generation = this.generation;
    let consumed = false;
    this.pending = this.clock.request(timestamp => {
      if (consumed || generation !== this.generation || !this.running()) return;
      consumed = true; this.pending = null;
      const previous = this.timestamp;
      if (Number.isFinite(timestamp) && (previous === null || timestamp >= previous)) {
        this.timestamp = timestamp;
        this.state = this.freeze({ ...this.state, animation: advanceElapsed(this.state.animation,
          previous === null ? 0 : timestamp - previous, this.state.speed,
          { recoilTime: this.descriptor!.recoilTime, cooldownTime: this.descriptor!.cooldownTime, moving: this.state.moving }) });
        this.publish();
      }
      // Listener may synchronously dispose, hide, pause, or switch content.
      if (generation === this.generation && this.running()) this.schedule();
    });
  }
}
