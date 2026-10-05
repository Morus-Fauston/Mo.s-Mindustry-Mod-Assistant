import { describe, expect, it } from 'vitest';
import { decodeFieldKey, encodeFieldKey, moveBefore, scopedFields } from './address';
import type { FormField } from '../forms/types';

const first = 'a'.repeat(32), second = 'b'.repeat(32), third = 'c'.repeat(32);
describe('嵌套字段公开地址', () => {
  it('顶层兼容旧草稿键，重复项依靠服务端身份隔离', () => {
    expect(encodeFieldKey([], 'health')).toBe('health');
    const path = ['bullet', 'spawnBullets', { itemId: first }];
    const key = encodeFieldKey(path, 'damage');
    expect(decodeFieldKey(key)).toEqual({ objectPath: path, field: 'damage' });
    const other = encodeFieldKey(['bullet', 'spawnBullets', { itemId: second }], 'damage');
    expect(key).not.toBe(other);
    expect(scopedFields({ [key]: '1e-', [other]: '8', health: '100' }, path, [{ name: 'damage' } as FormField])).toEqual({ damage: '1e-' });
  });
  it('拒绝旧数组下标与不完整地址', () => {
    for (const key of ['bullet.damage', '@nested:not-json', '@nested:[["bullet","0"],"damage"]', '@nested:[[0],"damage"]']) {
      expect(() => decodeFieldKey(key)).toThrow('字段地址无效');
    }
  });
  it('移动动作发送项身份与目标锚点，保留末尾语义', () => {
    const items = [first, second, third].map(itemId => ({ itemId }));
    expect(moveBefore(items, first, 'up')).toBeUndefined();
    expect(moveBefore(items, first, 'down')).toBe(third);
    expect(moveBefore(items, second, 'up')).toBe(first);
    expect(moveBefore(items, second, 'down')).toBeNull();
    expect(moveBefore(items, third, 'down')).toBeUndefined();
  });
});
