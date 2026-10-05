/** Pure view mathematics; scene coordinates have already applied PPU and inverted Y. */
export interface AnimationState {
  readonly timeTick: number;
  readonly recoil: number;
  readonly heat: number;
  readonly muzzleFlashTicks: number;
  readonly treadTime: number;
}
export interface AnimationTiming { recoilTime: number; cooldownTime: number; moving: boolean }
export const initialAnimation = (): AnimationState => ({ timeTick: 0, recoil: 0, heat: 0, muzzleFlashTicks: 0, treadTime: 0 });
export const fireAnimation = (state: AnimationState): AnimationState => ({ ...state, recoil: 1, heat: 1, muzzleFlashTicks: 3 });
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max));
const finite = (value: number, fallback = 0) => Number.isFinite(value) ? value : fallback;

/** One reference step, matching PreviewAnimationState.advance's three-tick cap. */
export function advanceAnimation(state: AnimationState, ticks: number, timing: AnimationTiming): AnimationState {
  const delta = clamp(finite(ticks), 0, 3);
  return {
    timeTick: state.timeTick + delta,
    recoil: Math.max(0, state.recoil - delta / Math.max(finite(timing.recoilTime, 10), 1)),
    heat: Math.max(0, state.heat - delta / Math.max(finite(timing.cooldownTime, 20), 1)),
    muzzleFlashTicks: Math.max(0, state.muzzleFlashTicks - delta),
    treadTime: state.treadTime + (timing.moving ? delta : 0),
  };
}

/** At most 100 ms of foreground wall time; retain elapsed time at low frame rates. */
export function advanceElapsed(state: AnimationState, elapsedMs: number, speed: 0.5 | 1 | 2, timing: AnimationTiming): AnimationState {
  let remaining = clamp(finite(elapsedMs), 0, 100) * 0.06 * speed;
  let next = state;
  while (remaining > 0) {
    const delta = Math.min(remaining, 3);
    next = advanceAnimation(next, delta, timing);
    remaining -= delta;
  }
  return next;
}

export function pulse(timeTick: number, scale = 2, magnitude = 1): number {
  return (Math.sin(timeTick / (2 * Math.max(scale, 0.001))) * magnitude + magnitude) / 2;
}
export const recoilOffset = (state: AnimationState, distance = 1, power = 1.8): number =>
  -(Math.max(state.recoil, 0) ** Math.max(power, 0)) * distance;
export const flashOpacity = (state: AnimationState): number => clamp(state.muzzleFlashTicks / 3, 0, 1);
export const treadFrame = (state: AnimationState, frames: number): number => Math.trunc(state.treadTime) % Math.max(Math.trunc(frames), 1);

/** Python round uses ties-to-even, unlike JavaScript Math.round. */
function roundEven(value: number): number {
  const floor = Math.floor(value);
  return value - floor === 0.5 ? floor + floor % 2 : Math.round(value);
}
export function cellColor(teamColor: string, healthFraction: number, timeTick: number): string {
  const fraction = clamp(healthFraction, 0, 1);
  const amount = clamp(fraction + pulse(timeTick, Math.max(fraction * 5, 1), 1 - fraction), 0, 1);
  return '#' + [1, 3, 5].map(offset => roundEven(parseInt(teamColor.slice(offset, offset + 2), 16) * amount).toString(16).padStart(2, '0')).join('');
}
