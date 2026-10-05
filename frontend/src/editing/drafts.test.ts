import { describe, expect, it } from 'vitest';
import { createDraftStore } from './drafts';

describe('表单草稿与真实提交边界', () => {
  it('串行提交不同字段，交给后端解析文本', async () => {
    const calls: string[] = [];
    let running = false;
    const store = createDraftStore(async (path, field, text) => {
      expect(running).toBe(false); running = true;
      await Promise.resolve(); calls.push(`${path}:${field}:${text}`); running = false;
    });
    store.set('a', 'health', '2.5'); store.set('b', 'description', '中文');
    await Promise.all([store.commit('a', 'health'), store.flush()]);
    expect(calls).toEqual(['a:health:2.5', 'b:description:中文']);
    expect(store.getSnapshot().drafts).toEqual({});
  });

  it('失败保留原始输入和字段错误，改正后才清除', async () => {
    const store = createDraftStore(async (_path, _field, text) => {
      if (text === '-') throw new Error('数值不完整');
    });
    store.set('a', 'health', '-');
    await expect(store.flush()).rejects.toThrow('数值不完整');
    expect(store.getSnapshot().drafts.a.health).toBe('-');
    expect(store.getSnapshot().errors.a.health).toBe('数值不完整');
    store.set('a', 'health', '10'); await store.flush();
    expect(store.getSnapshot().drafts).toEqual({});
    expect(store.getSnapshot().errors).toEqual({});
  });

  it('提交中继续输入不会被旧成功响应吞掉', async () => {
    let resolve!: () => void;
    const store = createDraftStore(() => new Promise<void>(done => { resolve = done; }));
    store.set('a', 'description', '第一稿');
    const pending = store.commit('a', 'description'); await Promise.resolve();
    store.set('a', 'description', '第二稿'); resolve(); await pending;
    expect(store.getSnapshot().drafts.a.description).toBe('第二稿');
  });

  it('切工程后旧失败和排队操作都不能污染新草稿', async () => {
    let reject!: (error: Error) => void;
    let calls = 0;
    const store = createDraftStore(() => { calls++; return new Promise<void>((_done, fail) => { reject = fail; }); });
    store.set('a', 'health', '12');
    const first = store.commit('a', 'health'); await Promise.resolve();
    const queued = store.flush();
    store.reset(); store.set('a', 'health', '88');
    reject(new Error('旧工程失败'));
    await expect(first).rejects.toThrow('旧工程失败'); await queued;
    expect(calls).toBe(1);
    expect(store.getSnapshot().drafts.a.health).toBe('88');
    expect(store.getSnapshot().errors).toEqual({});
  });

  it('中文组合期间不可提交，结束后提交最终文本', async () => {
    const values: string[] = [];
    const store = createDraftStore(async (_path, _field, text) => { values.push(text); });
    store.set('a', 'description', 'zhong'); store.composition('a', 'description', true);
    await expect(store.flush()).rejects.toThrow('中文输入'); expect(values).toEqual([]);
    store.set('a', 'description', '中文'); store.composition('a', 'description', false);
    await store.flush(); expect(values).toEqual(['中文']);
  });

  it('关闭目标文档只清理其草稿与组合状态', () => {
    const store = createDraftStore(async () => {});
    store.set('a', 'health', '12'); store.set('b', 'description', '留存');
    store.composition('a', 'health', true); store.removePaths(['a']);
    expect(store.getSnapshot().drafts).toEqual({ b: { description: '留存' } });
    expect(store.getSnapshot().composing).toBe(false);
  });

  it('替换或删除字段可跳过该字段非法草稿，其他草稿仍提交', async () => {
    const calls: string[] = [];
    const store = createDraftStore(async (_path, field, text) => {
      if (text === 'invalid') throw new Error('非法颜色');
      calls.push(field);
    });
    store.set('a', 'outlineColor', 'invalid'); store.set('a', 'health', '12');
    await store.flush({ path: 'a', field: 'outlineColor' });
    expect(calls).toEqual(['health']);
    expect(store.getSnapshot().drafts.a.outlineColor).toBe('invalid');
  });
});
