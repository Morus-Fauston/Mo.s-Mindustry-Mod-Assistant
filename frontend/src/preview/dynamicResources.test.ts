import { expect, it } from 'vitest';
import { sceneResources } from './dynamicResources';
import type { PreviewScene } from './types';

it('把动态帧与热图纳入同一解码预算且保留静态资源', () => {
  const scene = { layers: [{ resourceId: 'body', width: 2, height: 3, tooltip: '主体' }], dynamic: {
    heat: { resourceId: 'heat', width: 2, height: 3, tooltip: '热图' },
    treads: { frames: [{ resourceId: 'frame', width: 4, height: 5 }] },
  } } as unknown as PreviewScene;
  expect(sceneResources(scene).map(item => item.resourceId)).toEqual(['body', 'heat', 'frame']);
  expect(sceneResources(null)).toEqual([]);
  expect(sceneResources({ ...scene, dynamic: undefined }).map(item => item.resourceId)).toEqual(['body']);
});
