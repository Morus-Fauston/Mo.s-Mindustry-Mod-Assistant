import { describe, expect, it } from 'vitest';
import { reconcileContentViews, affectedContentPaths } from './integration';

describe('权威内容变化与工作台视图', () => {
  it('重命名和逆向恢复同时移动源码视图，不保留失效路径', () => {
    const views = { old: { mode: 'source' as const, seen: true }, other: { mode: 'form' as const, seen: false } };
    const change = { action: 'rename' as const, beforePath: 'old', afterPath: 'new', undo: false };
    expect(reconcileContentViews(views, change, ['new', 'other'])).toEqual({ new: views.old, other: views.other });
    expect(reconcileContentViews({ new: views.old }, { ...change, undo: true }, ['old'])).toEqual({ old: views.old });
  });
  it('覆盖保留当前视图，删除清掉已关闭视图，恢复坏源码进入源码视图', () => {
    expect(reconcileContentViews({ a: { mode: 'source', seen: true } },
      { action: 'create', beforePath: 'a', afterPath: 'a', undo: false }, ['a'])).toEqual({ a: { mode: 'source', seen: true } });
    expect(reconcileContentViews({ a: { mode: 'source', seen: true } },
      { action: 'delete', beforePath: 'a', afterPath: null, undo: false }, [])).toEqual({});
    expect(reconcileContentViews({}, null, ['a'], ['a'])).toEqual({ a: { mode: 'source', seen: true } });
  });
  it('新建覆盖仅处理目标；新建工程处理全部；定位不处理草稿', () => {
    expect(affectedContentPaths('create_content', { category: 'units', name: 'same' }, ['x'])).toEqual(['content/units/same.json']);
    expect(affectedContentPaths('rename_content', { path: 'x' }, ['x', 'y'])).toEqual(['x']);
    expect(affectedContentPaths('create_project', {}, ['x', 'y'])).toEqual(['x', 'y']);
    expect(affectedContentPaths('reveal_content', { path: 'x' }, ['x'])).toEqual([]);
  });
});
