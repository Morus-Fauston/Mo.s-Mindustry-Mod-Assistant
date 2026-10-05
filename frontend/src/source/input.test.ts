import { afterEach, expect, it, vi } from 'vitest';
import { createSourceInput } from './input';

afterEach(() => vi.useRealTimers());

it('连续源码输入立即留下草稿，停止输入500ms后只提交最终文本', async () => {
  vi.useFakeTimers();
  let draft = '';
  const saved: string[] = [];
  const input = createSourceInput({
    onDraft: text => { draft = text; },
    onCommit: async () => { saved.push(draft); },
    onComposition: () => {},
  });
  input.change('{');
  await vi.advanceTimersByTimeAsync(400);
  input.change('{"name":"中文"}');
  expect(draft).toBe('{"name":"中文"}');
  await vi.advanceTimersByTimeAsync(499);
  expect(saved).toEqual([]);
  await vi.advanceTimersByTimeAsync(1);
  expect(saved).toEqual(['{"name":"中文"}']);
  await input.flush();
  expect(saved).toHaveLength(1);
  input.dispose();
});

it('中文组合期间不提交，组合结束后使用最终中文输入', async () => {
  vi.useFakeTimers();
  let draft = '';
  const saved: string[] = [], compositions: boolean[] = [];
  const input = createSourceInput({ onDraft: text => { draft = text; },
    onCommit: async () => { saved.push(draft); }, onComposition: active => compositions.push(active) });
  input.composition(true);
  input.change('{"name":"zhong"}');
  await vi.advanceTimersByTimeAsync(1000);
  await expect(input.flush()).rejects.toThrow('中文输入');
  expect(saved).toEqual([]);
  input.composition(false);
  input.change('{"name":"中文"}');
  await vi.advanceTimersByTimeAsync(500);
  expect(saved).toEqual(['{"name":"中文"}']);
  expect(compositions).toEqual([true, false]);
  input.dispose();
});

it('提交过程中继续输入不重复并发提交，也不被旧成功响应吞掉', async () => {
  vi.useFakeTimers();
  let draft = '', finish!: () => void;
  const saved: string[] = [];
  const input = createSourceInput({ onDraft: text => { draft = text; }, onComposition: () => {},
    onCommit: async () => { saved.push(draft); if (saved.length === 1) await new Promise<void>(resolve => { finish = resolve; }); } });
  input.change('第一稿');
  await vi.advanceTimersByTimeAsync(500);
  input.change('第二稿');
  await vi.advanceTimersByTimeAsync(500);
  expect(saved).toEqual(['第一稿']);
  finish();
  await vi.advanceTimersByTimeAsync(500);
  expect(saved).toEqual(['第一稿', '第二稿']);
  input.dispose();
});

it('切会话销毁旧输入器会解除组合标记，旧提交结束不能再调度新请求', async () => {
  vi.useFakeTimers();
  let finish!: () => void;
  const saved: string[] = [], compositions: boolean[] = [];
  let draft = '';
  const input = createSourceInput({ onDraft: text => { draft = text; }, onComposition: value => compositions.push(value),
    onCommit: async () => { saved.push(draft); await new Promise<void>(resolve => { finish = resolve; }); } });
  input.change('第一稿'); await vi.advanceTimersByTimeAsync(500);
  input.composition(true); input.change('未完成组合'); input.dispose();
  finish(); await vi.advanceTimersByTimeAsync(2000);
  input.change('旧回调'); input.composition(false); await input.flush();
  expect(saved).toEqual(['第一稿']);
  expect(draft).toBe('未完成组合');
  expect(compositions).toEqual([true, false]);
});

it('输入无效后草稿保留，不自动重试，下一次明确修改可以提交', async () => {
  vi.useFakeTimers();
  let draft = '', attempts = 0;
  const saved: string[] = [];
  const input = createSourceInput({ onDraft: text => { draft = text; }, onComposition: () => {},
    onCommit: async () => { attempts++; if (draft === '{') throw new Error('JSON 语法无效'); saved.push(draft); } });
  input.change('{'); await vi.advanceTimersByTimeAsync(2000);
  expect(draft).toBe('{'); expect(attempts).toBe(1);
  input.change('{}'); await vi.advanceTimersByTimeAsync(500);
  expect(saved).toEqual(['{}']); input.dispose();
});

it('连接忙碌时暂停定时提交，恢复可编辑后继续，销毁后不再恢复', async () => {
  vi.useFakeTimers();
  const commit = vi.fn(async () => {});
  const input = createSourceInput({ onDraft: () => {}, onComposition: () => {}, onCommit: commit });
  input.change('{}'); input.setEnabled(false);
  await vi.advanceTimersByTimeAsync(2000);
  expect(commit).not.toHaveBeenCalled();
  input.setEnabled(true); await vi.advanceTimersByTimeAsync(500);
  expect(commit).toHaveBeenCalledTimes(1);
  input.change('{"x":1}'); input.dispose(); input.setEnabled(true);
  await vi.advanceTimersByTimeAsync(2000);
  expect(commit).toHaveBeenCalledTimes(1);
});

it('失败请求解除忙碌不能触发无限自动重试', async () => {
  vi.useFakeTimers();
  let attempts = 0;
  const input = createSourceInput({ onDraft: () => {}, onComposition: () => {}, onCommit: async () => {
    attempts++; input.setEnabled(false); await Promise.resolve(); input.setEnabled(true);
    throw new Error('第 1 行第 2 列：JSON 语法无效。');
  } });
  input.change('{'); await vi.advanceTimersByTimeAsync(5000);
  expect(attempts).toBe(1); input.dispose();
});
