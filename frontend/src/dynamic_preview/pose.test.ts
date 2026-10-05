import { describe, expect, it } from 'vitest';
import { poseScene, rotatePoint } from './pose';
import { initialDynamicState } from './controller';
import { fireAnimation } from './math';
import type { DynamicPreviewDescriptor } from './types';
import type { PreviewLayer, PreviewScene } from '../preview/types';

const layer = (key: string, x = 40, flipX = false): PreviewLayer => ({ key, nodeId: key.startsWith('weapon') ? 'weapon:0' : `sprite:${key}`,
  resourceId: `png:${key}`, x, y: 30, width: 20, height: 20, z: 1, flipX, tooltip: key });
const scene: PreviewScene = { sessionId: 's', width: 100, height: 80, status: 'ready', warnings: [],
  layers: [layer(''), layer('-team'), layer('-cell'), layer('-treads'), layer('-heat'), layer('weapon', 10), layer('weapon', 70, true)],
  circles: [ { key: 'outer', nodeId: 'engine', cx: 50, cy: 70, radius: 8, z: -1, color: '#ffaa00', tooltip: '' },
    { key: 'inner', nodeId: 'engine', cx: 50, cy: 68, radius: 4, z: -1, color: '#ffffff', tooltip: '' } ],
};
const descriptor: DynamicPreviewDescriptor = { supported: true, notices: [], recoilTime: 10, cooldownTime: 20,
  teams: [{ value: '蓝队', label: '蓝队', color: '#50a9ee' }], healthLevels: [{ value: '残血', label: '残血', fraction: 0.15 }],
  directions: [{ value: '右', label: '右', degrees: 90 }], teamLayerKeys: ['-team'], cellLayerKeys: ['-cell'],
  weapons: [{ nodeId: 'weapon:0', layerKeys: ['weapon'], recoilDistance: 2, recoilPower: 1.8, flashCenter: { x: 20, y: 40 } }],
  engine: { nodeId: 'engine', outerIndex: 0, innerIndex: 1, size: 2 },
  treads: { nodeId: 'sprite:-treads', layerKey: '-treads', frames: [{ resourceId: 'frame0', width: 10, height: 12 }, { resourceId: 'frame1', width: 12, height: 14 }] },
  heat: { ...layer('__heat__'), nodeId: 'sprite:-heat', z: 12, color: '#ff795e' }, flash: { radius: 3, color: '#fff3a1', z: 20 }, colorize: 'qt-colorize-strength-1',
};

describe('不可变动态场景', () => {
  it('开火0tick兼容旧镜像后坐、引擎内圈、单枪口和热图重复基线', () => {
    const before = JSON.stringify(scene);
    const state = { ...initialDynamicState(descriptor), enabled: true, moving: true, animation: fireAnimation(initialDynamicState().animation) };
    const pose = poseScene(scene, descriptor, state);
    expect(pose.layers.filter(item => item.key === 'weapon').map(item => [item.x, item.y, item.flipX, item.nodeId]))
      .toEqual([[10, 38, false, 'weapon:0'], [70, 38, true, 'weapon:0']]);
    expect(pose.circles.slice(0, 2).map(item => [item.cx, item.cy, item.radius])).toEqual([[50, 70, 9], [50, 67.75, 4.5]]);
    expect(pose.circles.filter(item => item.key.startsWith('__flash'))).toHaveLength(1);
    expect(pose.circles.at(-1)).toMatchObject({ cx: 20, cy: 40, radius: 3, opacity: 1, nodeId: 'weapon:0' });
    expect(pose.layers.filter(item => ['-heat', '__heat__'].includes(item.key))).toHaveLength(2);
    expect(pose.layers.find(item => item.key === '__heat__')).toMatchObject({ tintColor: '#ff795e', opacity: 1 });
    expect(pose.layers.find(item => item.key === '-treads')).toMatchObject({ resourceId: 'frame0', x: 45, y: 34, width: 10, height: 12 });
    expect(pose.layers.find(item => item.key === '-team')?.tintColor).toBe('#50a9ee');
    expect(pose.layers.find(item => item.key === '-cell')?.tintColor).toBe('#2e6189');
    expect(pose.rotationDegrees).toBe(90); expect(pose.center).toEqual({ x: 50, y: 40 });
    const rotated = rotatePoint({ x: 10, y: 38 }, pose.center, pose.rotationDegrees);
    expect(rotated.x).toBeCloseTo(52, 12); expect(rotated.y).toBeCloseTo(0, 12);
    expect(JSON.stringify(scene)).toBe(before);
  });
  it('静态模式原样保留场景，原地及未解码履带保留静态退路', () => {
    const initial = initialDynamicState(descriptor);
    const staticPose = poseScene(scene, descriptor, initial);
    expect(staticPose.layers).toBe(scene.layers); expect(staticPose.circles).toBe(scene.circles); expect(staticPose.rotationDegrees).toBe(0);
    const still = poseScene(scene, descriptor, { ...initial, enabled: true });
    expect(still.layers.find(item => item.key === '-treads')?.resourceId).toBe('png:-treads');
    const missing = poseScene(scene, descriptor, { ...initial, enabled: true, moving: true }, new Set(['png:-treads']));
    expect(missing.layers.find(item => item.key === '-treads')?.resourceId).toBe('png:-treads');
    expect(poseScene(scene, { ...descriptor, supported: false }, { ...initial, enabled: true }).layers).toBe(scene.layers);
  });
});
