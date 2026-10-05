import type { PreviewScene } from './types';

/** All frame resources use the same loader, budget and lifetime as the static scene. */
export function sceneResources(scene: PreviewScene | null) {
  if (!scene) return [];
  return [...scene.layers, ...(scene.dynamic?.heat ? [scene.dynamic.heat] : []),
    ...(scene.dynamic?.treads?.frames.map((frame, index) => ({ ...frame, tooltip: `履带帧 ${index + 1}` })) ?? [])];
}
