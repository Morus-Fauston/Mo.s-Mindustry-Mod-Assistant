import { expect, it } from 'vitest';
import { createNestedRevealTracker } from './reveal';

it('一次请求逐层打开匹配的对象与数组，兄弟节点不消费且刷新不重放', () => {
  const itemId = 'a'.repeat(32);
  const request = { token: 3, objectPath: ['weapons', { itemId }, 'bullet'], field: 'damage' };
  const reveal = createNestedRevealTracker();
  expect(reveal.consume(request, ['abilities'], false)).toBe(false);
  expect(reveal.consume(request, ['weapons'], true)).toBe(false);
  expect(reveal.consume(request, ['weapons'], false)).toBe(true);
  expect(reveal.consume(request, ['weapons', { itemId }, 'bullet'], false)).toBe(true);
  expect(reveal.consume({ ...request }, ['weapons'], false)).toBe(false);
  expect(reveal.consume({ ...request }, ['weapons', { itemId }, 'bullet'], false)).toBe(false);
  expect(reveal.consume({ ...request, token: 4 }, ['weapons'], false)).toBe(true);
  expect(reveal.consume(request, ['weapons'], false)).toBe(false);
});

it('字段本身可展开，但相同位置的不同数组身份和无效请求不能触发', () => {
  const reveal = createNestedRevealTracker();
  const request = { token: 1, objectPath: ['weapons', { itemId: 'a'.repeat(32) }], field: 'bullet' };
  expect(reveal.consume(request, ['weapons', { itemId: 'b'.repeat(32) }, 'bullet'], false)).toBe(false);
  expect(reveal.consume(request, [...request.objectPath, 'bullet'], false)).toBe(true);
  expect(reveal.consume(undefined, ['weapons'], false)).toBe(false);
  expect(reveal.consume({ ...request, token: Number.NaN }, ['weapons'], false)).toBe(false);
});
