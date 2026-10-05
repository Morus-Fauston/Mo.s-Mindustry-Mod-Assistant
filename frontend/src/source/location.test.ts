import { EditorState } from '@codemirror/state';
import { expect, it, vi } from 'vitest';
import { createSourceLocator, sourceOffset } from './location';

it('Python 的一基 Unicode 码点列定位到 CodeMirror 的 UTF-16 光标', () => {
  const doc = EditorState.create({ doc: '首行\nA𝄞中e\u0301尾\n结束' }).doc;
  expect(sourceOffset(doc, 2, 1)).toBe(3);
  expect(sourceOffset(doc, 2, 3)).toBe(6);
  expect(sourceOffset(doc, 2, 6)).toBe(9);
});

it('行列越界限制在真实文档内，非法数字不定位', () => {
  const doc = EditorState.create({ doc: '首\r\n𝄞尾\r\n' }).doc;
  expect(sourceOffset(doc, -2, -1)).toBe(0);
  expect(sourceOffset(doc, 2, 100)).toBe(5);
  expect(sourceOffset(doc, 100, 100)).toBe(6);
  expect(sourceOffset(doc, Number.NaN, 1)).toBeNull();
  expect(sourceOffset(doc, 1, 2.5)).toBeNull();
  expect(sourceOffset(EditorState.create().doc, 1, 1)).toBe(0);
});

it('定位仅在可见可用时消费 token，滚动聚焦但不产生文本修改', () => {
  let state = EditorState.create({ doc: '首\nA𝄞尾' });
  let visible = false;
  let visibility = 'visible';
  let composing = false;
  const focused = vi.fn();
  const transactions: ReturnType<typeof state.update>[] = [];
  const view = {
    get state() { return state; },
    dom: { getClientRects: () => ({ length: visible ? 1 : 0 }),
      ownerDocument: { defaultView: { getComputedStyle: () => ({ visibility }) } } },
    get composing() { return composing; },
    dispatch: (spec: Parameters<typeof state.update>[0]) => {
      const transaction = state.update(spec); transactions.push(transaction); state = transaction.state;
    },
    focus: focused,
  } as unknown as Parameters<ReturnType<typeof createSourceLocator>>[0];
  const reveal = createSourceLocator();
  const request = { token: 1, line: 2, column: 3 };
  expect(reveal(view, request, false)).toBe(false);
  visible = true;
  expect(reveal(view, request, true)).toBe(false);
  visibility = 'hidden';
  expect(reveal(view, request, false)).toBe(false);
  visibility = 'visible'; composing = true;
  expect(reveal(view, request, false)).toBe(false);
  composing = false;
  expect(reveal(view, { ...request, line: Number.NaN }, false)).toBe(false);
  expect(reveal(view, request, false)).toBe(true);
  expect(state.selection.main.head).toBe(5);
  expect(focused).toHaveBeenCalledTimes(1);
  expect(transactions).toHaveLength(1);
  expect(transactions[0].docChanged).toBe(false);
  expect(transactions[0].scrollIntoView).toBe(true);
  expect(state.doc.toString()).toBe('首\nA𝄞尾');
  expect(reveal(view, { ...request }, false)).toBe(false);
  expect(reveal(view, { ...request, token: 2 }, false)).toBe(true);
  expect(reveal(view, request, false)).toBe(false);
  expect(focused).toHaveBeenCalledTimes(2);
});
