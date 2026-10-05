import type { PreviewCircle, PreviewLayer, PreviewScene } from '../preview/types';
import { cellColor, flashOpacity, pulse, recoilOffset, treadFrame } from './math';
import type { DynamicPreviewDescriptor, DynamicPreviewState } from './types';

export interface DynamicLayer extends PreviewLayer { tintColor?: string; opacity?: number }
export interface DynamicCircle extends PreviewCircle { opacity?: number }
export interface DynamicPose {
  layers: DynamicLayer[];
  circles: DynamicCircle[];
  rotationDegrees: number;
  center: { x: number; y: number };
}

export function rotatePoint(point: { x: number; y: number }, center: { x: number; y: number }, degrees: number) {
  const radians = degrees * Math.PI / 180, cosine = Math.cos(radians), sine = Math.sin(radians);
  return { x: center.x + (point.x - center.x) * cosine - (point.y - center.y) * sine,
    y: center.y + (point.x - center.x) * sine + (point.y - center.y) * cosine };
}

/** Geometry only: the renderer owns decoding, tint pixel composition, visibility and disposal. */
export function poseScene(scene: PreviewScene, descriptor: DynamicPreviewDescriptor | null, state: DynamicPreviewState,
  availableResources?: ReadonlySet<string>): DynamicPose {
  const center = { x: scene.width / 2, y: scene.height / 2 };
  if (!state.enabled || !descriptor?.supported) return { layers: scene.layers, circles: scene.circles, rotationDegrees: 0, center };
  const team = descriptor.teams.find(item => item.value === state.team) ?? descriptor.teams[0];
  const health = descriptor.healthLevels.find(item => item.value === state.health) ?? descriptor.healthLevels[0];
  const layers: DynamicLayer[] = scene.layers.map(layer => {
    let result: DynamicLayer = { ...layer };
    const weapon = descriptor.weapons.find(item => item.nodeId === layer.nodeId && item.layerKeys.includes(layer.key));
    // PPU=4, with world Y inverted exactly once. Mirror parts share the same recoil.
    if (weapon) result.y -= recoilOffset(state.animation, weapon.recoilDistance, weapon.recoilPower) * 4;
    if (team && descriptor.teamLayerKeys.includes(layer.key)) result.tintColor = team.color;
    if (team && health && descriptor.cellLayerKeys.includes(layer.key)) result.tintColor = cellColor(team.color, health.fraction, state.animation.timeTick);
    const treads = descriptor.treads;
    if (state.moving && treads && treads.layerKey === layer.key && treads.nodeId === layer.nodeId && treads.frames.length) {
      const frame = treads.frames[treadFrame(state.animation, treads.frames.length)];
      if (!availableResources || availableResources.has(frame.resourceId)) result = { ...result, ...frame,
        x: layer.x + (layer.width - frame.width) / 2, y: layer.y + (layer.height - frame.height) / 2 };
    }
    return result;
  });
  const circles: DynamicCircle[] = scene.circles.map(circle => ({ ...circle }));
  const engine = descriptor.engine;
  if (engine && circles[engine.outerIndex] && circles[engine.innerIndex]) {
    const outer = circles[engine.outerIndex], inner = circles[engine.innerIndex];
    outer.radius = engine.size * 4 * (1 + pulse(state.animation.timeTick) / 4);
    inner.radius = outer.radius / 2;
    inner.cy = outer.cy - outer.radius / 4;
  }
  const heat = descriptor.heat;
  if (heat && state.animation.heat > 0 && (!availableResources || availableResources.has(heat.resourceId))) {
    layers.push({ ...heat, tintColor: heat.color, opacity: Math.max(0, Math.min(1, state.animation.heat)) });
  }
  const opacity = flashOpacity(state.animation);
  if (opacity > 0) for (const [index, weapon] of descriptor.weapons.entries()) {
    circles.push({ key: `__flash_${index}__`, nodeId: weapon.nodeId, cx: weapon.flashCenter.x, cy: weapon.flashCenter.y,
      radius: descriptor.flash.radius, color: descriptor.flash.color, z: descriptor.flash.z, tooltip: '开火示意', opacity });
  }
  return { layers, circles, rotationDegrees: descriptor.directions.find(item => item.value === state.direction)?.degrees
    ?? descriptor.directions[0]?.degrees ?? 0, center };
}
