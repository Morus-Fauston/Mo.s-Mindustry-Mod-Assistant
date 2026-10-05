import { describe, expect, it, vi } from 'vitest';
import { createContentToolsState } from './state';
import type { ContentCatalogue } from './types';

const catalogue: ContentCatalogue = { namePattern: '[a-z0-9-]+', nameHint: '核心名称规则', categories: [
  { id: 'units', label: '单位', templates: [{ kind: 'UnitType-flying', label: '飞行单位' }] },
  { id: 'blocks', label: '方块', templates: [{ kind: 'Wall', label: '墙', group: '防御' }] },
] };

describe('内容工具的公开操作边界', () => {
  it('超时原操作恢复后关闭对话框，迟到失败不覆盖新输入', async () => {
    let reject!: (error: Error) => void;
    const state = createContentToolsState({ loadCatalogue: async () => catalogue,
      onAction: () => new Promise<void>((_resolve, fail) => { reject = fail; }) });
    state.session('s'); await state.open('rename_content', 'content/units/a.json');
    state.update('name', 'b'); const pending = state.submit();
    state.complete();
    expect(state.getSnapshot()).toMatchObject({ mode: null, submitting: false });
    await state.open('create_content', null); state.update('name', 'fresh');
    reject(new Error('旧结果')); await pending;
    expect(state.getSnapshot()).toMatchObject({ mode: 'create_content', error: '', form: { name: 'fresh' } });
  });
  it('从真实目录选择模板；取消不发起写操作', async () => {
    const action = vi.fn(async () => {});
    const state = createContentToolsState({ loadCatalogue: async () => catalogue, onAction: action });
    state.session('s'); await state.open('create_content', null);
    expect(state.getSnapshot().form.kind).toBe('UnitType-flying');
    state.update('category', 'blocks');
    expect(state.getSnapshot().form.kind).toBe('Wall');
    state.cancel();
    expect(state.getSnapshot().mode).toBeNull();
    expect(action).not.toHaveBeenCalled();
  });

  it('提交期间拒绝重复动作和取消，后端失败保留输入及错误', async () => {
    let reject!: (error: Error) => void;
    const action = vi.fn(() => new Promise<void>((_resolve, fail) => { reject = fail; }));
    const state = createContentToolsState({ loadCatalogue: async () => catalogue, onAction: action });
    state.session('s'); await state.open('create_content', null); state.update('name', 'my-unit');
    const first = state.submit();
    await state.submit(); state.cancel();
    expect(action).toHaveBeenCalledOnce();
    expect(action).toHaveBeenCalledWith('create_content', { category: 'units', kind: 'UnitType-flying', name: 'my-unit', overwrite: false });
    expect(state.getSnapshot().mode).toBe('create_content');
    reject(new Error('文件被占用')); await first;
    expect(state.getSnapshot()).toMatchObject({ error: '文件被占用', submitting: false, mode: 'create_content' });
    expect(state.getSnapshot().form.name).toBe('my-unit');
  });

  it('FILE_EXISTS不会自动覆盖，必须再次明确确认；修改名称后撤销覆盖资格', async () => {
    const action = vi.fn(async (_action: unknown, payload: Record<string, unknown>) => {
      if (!payload.overwrite) throw Object.assign(new Error('文件已存在'), { code: 'FILE_EXISTS' });
    });
    const state = createContentToolsState({ loadCatalogue: async () => catalogue, onAction: action });
    state.session('s'); await state.open('create_content', null); state.update('name', 'my-unit');
    await state.submit(true); expect(action).not.toHaveBeenCalled();
    await state.submit();
    expect(state.getSnapshot().conflict).toBe(true);
    expect(action).toHaveBeenCalledOnce();
    state.update('name', 'other-unit');
    await state.submit(true); expect(action).toHaveBeenCalledOnce();
    await state.submit(); await state.submit(true);
    expect(action).toHaveBeenLastCalledWith('create_content', { category: 'units', kind: 'UnitType-flying', name: 'other-unit', overwrite: true });
    expect(state.getSnapshot().mode).toBeNull();
  });

  it('切工程后旧提交失败与旧目录不能污染新对话框', async () => {
    let fail!: (error: Error) => void;
    const state = createContentToolsState({ loadCatalogue: async () => catalogue,
      onAction: () => new Promise<void>((_resolve, reject) => { fail = reject; }) });
    state.session('old'); await state.open('rename_content', 'content/units/old.json');
    state.update('name', 'new'); const pending = state.submit();
    state.session('new'); await state.open('create_content', null); state.update('name', 'fresh');
    fail(new Error('旧会话失败')); await pending;
    expect(state.getSnapshot()).toMatchObject({ sessionId: 'new', mode: 'create_content', error: '', submitting: false });
    expect(state.getSnapshot().form.name).toBe('fresh');

    let release!: (value: ContentCatalogue) => void;
    const late = createContentToolsState({ loadCatalogue: () => new Promise(resolve => { release = resolve; }), onAction: async () => {} });
    late.session('old'); const loading = late.open('create_content', null);
    late.session('new'); release(catalogue); await loading;
    expect(late.getSnapshot()).toMatchObject({ mode: null, catalogue: null, loading: false });
  });

  it('删除固定弹窗打开时的实际路径，不依赖目录读取；新建工程不发送路径', async () => {
    const action = vi.fn(async () => {}), load = vi.fn(async () => catalogue);
    const state = createContentToolsState({ loadCatalogue: load, onAction: action });
    state.session('s'); await state.open('delete_content', 'content/weapons/same.json');
    expect(load).not.toHaveBeenCalled();
    await state.submit();
    expect(action).toHaveBeenLastCalledWith('delete_content', { path: 'content/weapons/same.json', confirmed: true });
    state.session(null); await state.open('create_project', null);
    state.update('modId', 'my-mod'); state.update('displayName', '我的模组'); state.update('author', '作者');
    await state.submit();
    expect(action).toHaveBeenLastCalledWith('create_project', { mod_id: 'my-mod', displayName: '我的模组', author: '作者' });
  });

  it('读取失败后重试保留名称', async () => {
    let reads = 0;
    const load = vi.fn(async () => { if (++reads === 1) throw new Error('离线资料读取失败'); return catalogue; });
    const state = createContentToolsState({ loadCatalogue: load, onAction: async () => {} });
    state.session('s'); await state.open('create_content', null); state.update('name', 'keep-name');
    await state.reload();
    expect(state.getSnapshot()).toMatchObject({ error: '', loading: false });
    expect(state.getSnapshot().form.name).toBe('keep-name');
    expect(state.getSnapshot().form.kind).toBe('UnitType-flying');
  });

  it('取消和卸载都使迟到的目录结果失效', async () => {
    let release!: (value: ContentCatalogue) => void;
    const state = createContentToolsState({ loadCatalogue: () => new Promise(resolve => { release = resolve; }), onAction: async () => {} });
    state.session('s'); const opening = state.open('create_content', null);
    state.cancel(); release(catalogue); await opening;
    expect(state.getSnapshot()).toMatchObject({ mode: null, catalogue: null, loading: false });
    const next = state.open('create_content', null);
    const listener = vi.fn(), unsubscribe = state.subscribe(listener);
    state.dispose(); release(catalogue); await next;
    expect(listener).not.toHaveBeenCalled();
    unsubscribe();
  });
});
