import { describe, expect, it, vi } from 'vitest';
import { createComparisonController } from './controller';
import type { CandidatePage, Comparison, ComparisonCallbacks, SourceDescriptor } from './types';

const source = (id: string): SourceDescriptor => ({ sourceId: id, kind: id === 'vanilla' ? 'vanilla' : 'zip',
  label: id, categories: [{ id: 'units', label: '单位' }], warnings: [] });
const result = (id = 'first', revision = 1, sessionId = '甲', currentPath = 'current.json'): Comparison => ({
  sessionId, currentPath, revision, sourceId: id, category: 'units', name: 'unit', rows: [],
});
function actions(): ComparisonCallbacks {
  return { onOpen: vi.fn(async () => source('first')), onSources: vi.fn(async () => ({ sources: [source('vanilla')] })),
    onCandidates: vi.fn(async (sourceId, category) => ({ sourceId, category, candidates: [], offset: 0, total: 0, hasMore: false })),
    onCompare: vi.fn(async (id) => result(id)), onRelease: vi.fn(async () => {}) };
}

describe('只读比较来源生命周期', () => {
  it('编辑忙或草稿未提交时只标陈旧，解除门禁后自动比较最新修订且不循环重试', async () => {
    const callbacks = actions(), controller = createComparisonController();
    controller.start('甲', 'current.json', 1, callbacks);
    await controller.open('zip'); await controller.compare('first', 'units', 'unit');
    const latest = actions(); latest.onCompare = vi.fn(async id => result(id, 2));
    controller.updateContext('current.json', 2, latest, false);
    expect(latest.onCompare).not.toHaveBeenCalled();
    expect(controller.getSnapshot().stale).toBe(true);
    controller.updateContext('current.json', 2, latest, true);
    await Promise.resolve(); await Promise.resolve();
    expect(controller.getSnapshot().comparison?.revision).toBe(2);
    expect(latest.onCompare).toHaveBeenCalledTimes(1);
    controller.updateContext('current.json', 2, latest, true);
    expect(latest.onCompare).toHaveBeenCalledTimes(1);
  });
  it('新来源先待选，比较失败或取消保留旧比较，成功后才释放旧来源', async () => {
    const callbacks = actions(), controller = createComparisonController();
    controller.start('甲', 'current.json', 1, callbacks);
    await controller.loadSources(); await controller.open('zip');
    expect(controller.getSnapshot().pending?.sourceId).toBe('first');
    await controller.compare('first', 'units', 'unit');
    expect(controller.getSnapshot().comparison?.sourceId).toBe('first');
    vi.mocked(callbacks.onOpen).mockResolvedValue(source('second'));
    await controller.open('folder');
    vi.mocked(callbacks.onCompare).mockRejectedValueOnce(new Error('读取失败'));
    await controller.compare('second', 'units', 'unit');
    expect(controller.getSnapshot().comparison?.sourceId).toBe('first');
    expect(controller.getSnapshot().error).toBe('读取失败');
    expect(callbacks.onRelease).not.toHaveBeenCalled();
    await controller.cancelPending();
    expect(callbacks.onRelease).toHaveBeenCalledWith('second');
    expect(controller.getSnapshot().comparison?.sourceId).toBe('first');
    await controller.candidates('first', 'units', '');
    expect(controller.getSnapshot().notice).toBe('已取消待选参考，原对比保持不变。');
    await controller.open('zip'); await controller.compare('second', 'units', 'unit');
    expect(controller.getSnapshot().comparison?.sourceId).toBe('second');
    expect(callbacks.onRelease).toHaveBeenCalledWith('first');
  });

  it('修订刷新保留待选来源，旧修订比较回包不能覆盖新文档', async () => {
    const callbacks = actions(), controller = createComparisonController();
    controller.start('甲', 'current.json', 1, callbacks);
    await controller.open('zip'); await controller.compare('first', 'units', 'unit');
    vi.mocked(callbacks.onOpen).mockResolvedValue(source('pending'));
    await controller.open('zip');
    let finish!: (value: Comparison) => void;
    callbacks.onCompare = vi.fn(() => new Promise<Comparison>(resolve => { finish = resolve; }));
    controller.updateContext('current.json', 2, callbacks);
    await Promise.resolve();
    expect(controller.getSnapshot().stale).toBe(true);
    const latest = actions(); latest.onCompare = vi.fn(async id => result(id, 3, '甲', 'next.json'));
    controller.updateContext('next.json', 3, latest);
    await Promise.resolve(); await Promise.resolve();
    finish(result('first', 2)); await Promise.resolve();
    expect(controller.getSnapshot().comparison?.currentPath).toBe('next.json');
    expect(controller.getSnapshot().pending?.sourceId).toBe('pending');
    expect(callbacks.onRelease).not.toHaveBeenCalled();
  });

  it('卸载后迟到导入通过旧回调释放，新会话不受影响', async () => {
    let finish!: (value: SourceDescriptor) => void;
    const old = actions(), next = actions(), controller = createComparisonController();
    old.onOpen = vi.fn(() => new Promise<SourceDescriptor>(resolve => { finish = resolve; }));
    controller.start('甲', 'current.json', 1, old);
    const opening = controller.open('zip');
    controller.start('乙', 'next.json', 0, next);
    finish(source('late')); await opening;
    expect(old.onRelease).toHaveBeenCalledWith('late');
    expect(next.onRelease).not.toHaveBeenCalled();
    expect(controller.getSnapshot().sessionId).toBe('乙');
    expect(controller.getSnapshot().pending).toBeNull();
  });

  it('原生取消不改旧对比，重复导入和确认被门闩阻止', async () => {
    const callbacks = actions(), controller = createComparisonController();
    controller.start('甲', 'current.json', 1, callbacks);
    await controller.open('zip'); await controller.compare('first', 'units', 'unit');
    let finish!: (value: SourceDescriptor | null) => void;
    callbacks.onOpen = vi.fn(() => new Promise<SourceDescriptor | null>(resolve => { finish = resolve; }));
    const opening = controller.open('zip');
    await controller.open('folder'); await controller.compare('vanilla', 'units', 'unit');
    expect(callbacks.onOpen).toHaveBeenCalledTimes(1);
    finish(null); await opening;
    expect(controller.getSnapshot().notice).toContain('已取消');
    expect(controller.getSnapshot().comparison?.sourceId).toBe('first');
    expect(callbacks.onRelease).not.toHaveBeenCalled();
  });

  it('取消失败可重试；成功比较后的旧来源释放失败有可重试清理状态', async () => {
    const callbacks = actions(), controller = createComparisonController();
    controller.start('甲', 'current.json', 1, callbacks);
    await controller.open('zip');
    vi.mocked(callbacks.onRelease).mockRejectedValueOnce(new Error('释放失败'));
    await controller.cancelPending();
    expect(controller.getSnapshot().pending?.sourceId).toBe('first');
    expect(controller.getSnapshot().error).toBe('释放失败');
    await controller.compare('first', 'units', 'unit');
    vi.mocked(callbacks.onOpen).mockResolvedValue(source('second'));
    await controller.open('zip');
    vi.mocked(callbacks.onRelease).mockRejectedValueOnce(new Error('旧来源未释放'));
    await controller.compare('second', 'units', 'unit');
    expect(controller.getSnapshot().comparison?.sourceId).toBe('second');
    expect(controller.getSnapshot().cleanupNeeded).toBe(true);
    expect(controller.getSnapshot().error).toBe('旧来源未释放');
    await controller.retryCleanup();
    expect(controller.getSnapshot().cleanupNeeded).toBe(false);
  });

  it('卸载与进行中的取消共用一次释放，后台失败写入诊断', async () => {
    const callbacks = actions(), controller = createComparisonController();
    controller.start('甲', 'current.json', 1, callbacks); await controller.open('zip');
    let finish!: () => void;
    callbacks.onRelease = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
    const cancelling = controller.cancelPending(); controller.stop(); controller.stop();
    await Promise.resolve(); expect(callbacks.onRelease).toHaveBeenCalledTimes(1);
    finish(); await cancelling;
    const log = vi.spyOn(console, 'warn').mockImplementation(() => {});
    controller.start('甲', 'current.json', 1, callbacks); await controller.open('zip');
    callbacks.onRelease = vi.fn(async () => { throw new Error('关闭清理失败'); });
    controller.stop();
    await vi.waitFor(() => expect(log).toHaveBeenCalledWith(expect.stringContaining('清理失败'), '关闭清理失败'));
    log.mockRestore();
  });

  it('拒绝错误会话结果且保留待选，分页回包身份也必须匹配', async () => {
    const callbacks = actions(), controller = createComparisonController();
    controller.start('甲', 'current.json', 1, callbacks); await controller.open('zip');
    callbacks.onCompare = vi.fn(async () => result('first', 1, 'other'));
    await controller.compare('first', 'units', 'unit');
    expect(controller.getSnapshot().comparison).toBeNull();
    expect(controller.getSnapshot().pending?.sourceId).toBe('first');
    expect(controller.getSnapshot().error).toContain('不一致');
    callbacks.onCandidates = vi.fn(async () => ({ sourceId: 'wrong', category: 'units', candidates: [], offset: 0, total: 0, hasMore: false }));
    await controller.candidates('first', 'units', '', 0);
    expect(controller.getSnapshot().page).toBeNull();
    expect(controller.getSnapshot().error).toContain('不一致');
  });

  it('切会话后晚到候选不覆盖新列表，分页查询原样交给后端', async () => {
    const old = actions(), next = actions(), controller = createComparisonController();
    let finish!: (value: Awaited<ReturnType<ComparisonCallbacks['onCandidates']>>) => void;
    old.onCandidates = vi.fn(() => new Promise<CandidatePage>(resolve => { finish = resolve; }));
    controller.start('甲', 'current.json', 1, old);
    const reading = controller.candidates('vanilla', 'units', '中文 English', 100);
    expect(old.onCandidates).toHaveBeenCalledWith('vanilla', 'units', '中文 English', 100);
    controller.start('乙', 'next.json', 0, next);
    await controller.candidates('vanilla', 'units', '', 0);
    finish({ sourceId: 'vanilla', category: 'units', candidates: [], offset: 100, total: 101, hasMore: false });
    await reading;
    expect(controller.getSnapshot().page?.offset).toBe(0);
    expect(controller.getSnapshot().page?.total).toBe(0);
  });

  it('取消期间修订变化先完成释放，再用最新回调刷新当前对比', async () => {
    const callbacks = actions(), controller = createComparisonController();
    controller.start('甲', 'current.json', 1, callbacks);
    await controller.open('zip'); await controller.compare('first', 'units', 'unit');
    vi.mocked(callbacks.onOpen).mockResolvedValue(source('pending'));
    await controller.open('zip');
    let finish!: () => void;
    callbacks.onRelease = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
    const cancelling = controller.cancelPending(); await Promise.resolve();
    const latest = actions(); latest.onCompare = vi.fn(async id => result(id, 2));
    controller.updateContext('current.json', 2, latest);
    finish(); await cancelling; await Promise.resolve();
    expect(controller.getSnapshot().pending).toBeNull();
    expect(callbacks.onRelease).toHaveBeenCalledWith('pending');
    expect(latest.onRelease).not.toHaveBeenCalled();
    expect(latest.onCompare).toHaveBeenCalledWith('first', 'units', 'unit');
    expect(controller.getSnapshot().comparison?.revision).toBe(2);
  });
});
