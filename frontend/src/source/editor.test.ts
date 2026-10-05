import { EditorState } from '@codemirror/state';
import { undoDepth } from '@codemirror/commands';
import { expect, it } from 'vitest';
import { sourceEcho, forwardSourceChanges, sourceLanguage } from './editor';

it('后端回显只更新编辑器，真实输入才回传草稿，且不建立本地撤销历史', () => {
  let state = EditorState.create({ doc: '{"n":9007199254740993}', extensions: sourceLanguage() });
  const drafts: string[] = [];
  const echo = state.update(sourceEcho(state.doc.toString(), '{"n":9007199254740995}'));
  forwardSourceChanges([echo], value => drafts.push(value)); state = echo.state;
  expect(drafts).toEqual([]);
  expect(state.doc.toString()).toBe('{"n":9007199254740995}');
  const input = state.update({ changes: { from: 5, to: 21, insert: '12' } });
  forwardSourceChanges([input], value => drafts.push(value)); state = input.state;
  expect(drafts).toEqual(['{"n":12}']);
  expect(undoDepth(state)).toBe(0);
});

it('回显差异前的光标位置保持，中文文本不经过JSON解析重写', () => {
  const state = EditorState.create({ doc: '{"名称":"中文","n":1}', selection: { anchor: 8 } });
  const updated = state.update(sourceEcho(state.doc.toString(), '{"名称":"中文","n":12}')).state;
  expect(updated.selection.main.head).toBe(8);
  expect(updated.doc.toString()).toBe('{"名称":"中文","n":12}');
});
