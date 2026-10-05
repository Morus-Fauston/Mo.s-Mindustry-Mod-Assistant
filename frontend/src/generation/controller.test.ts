import { describe, expect, it, vi } from 'vitest';
import { createGenerationController } from './controller';
import type { GenerationCallbacks, GenerationCandidate } from './types';

const candidate = (sessionId = '甲', exists = false): GenerationCandidate => ({ sessionId, candidateId: `${sessionId}-候选`,
  outputs: [{ suffix: '-outline', label: '轮廓', path: 'sprites/units/单位-outline.png', exists, width: 16, height: 24, dataUrl: 'data:image/png;base64,cG5n' }] });
function callbacks(result = candidate()): GenerationCallbacks {
  return { onPreview: vi.fn(async () => result), onConfirm: vi.fn(async () => {}), onCancel: vi.fn(async () => {}) };
}
const outputs = [{ suffix: '-outline', options: { expandPx: 1, color: '#000000' } }];

describe('生成候选生命周期', () => {
  it('预览不确认写盘；取消只释放候选；确认成功清除候选', async () => {
    const actions = callbacks();
    const controller = createGenerationController();
    controller.start('甲/内容/1', '甲', actions);
    await controller.preview(outputs);
    expect(actions.onPreview).toHaveBeenCalledWith(outputs);
    expect(actions.onConfirm).not.toHaveBeenCalled();
    await controller.cancel();
    expect(actions.onCancel).toHaveBeenCalledWith('甲-候选');
    expect(controller.getSnapshot().candidate).toBeNull();
    await controller.preview(outputs); await controller.confirm(false);
    expect(actions.onConfirm).toHaveBeenCalledWith('甲-候选', false);
    expect(controller.getSnapshot().candidate).toBeNull();
    expect(controller.getSnapshot().confirmed).toBe(true);
  });

  it('覆盖必须明确确认，确认/取消失败保留候选且可重试', async () => {
    const actions = callbacks(candidate('甲', true));
    const controller = createGenerationController(); controller.start('甲', '甲', actions);
    await controller.preview(outputs); await controller.confirm(false);
    expect(actions.onConfirm).not.toHaveBeenCalled();
    vi.mocked(actions.onConfirm).mockRejectedValueOnce(new Error('来源变化'));
    await controller.confirm(true);
    expect(controller.getSnapshot().candidate?.candidateId).toBe('甲-候选');
    expect(controller.getSnapshot().error).toBe('来源变化');
    vi.mocked(actions.onCancel).mockRejectedValueOnce(new Error('释放失败'));
    await controller.cancel();
    expect(controller.getSnapshot().candidate).not.toBeNull();
    expect(controller.getSnapshot().error).toBe('释放失败');
    await controller.cancel(); expect(controller.getSnapshot().candidate).toBeNull();
  });

  it('重复预览被门闩拦截，已有候选不能被隐式丢弃', async () => {
    let finish!: (value: GenerationCandidate) => void;
    const actions = callbacks(); actions.onPreview = vi.fn(() => new Promise<GenerationCandidate>(resolve => { finish = resolve; }));
    const controller = createGenerationController(); controller.start('甲', '甲', actions);
    const pending = controller.preview(outputs); await controller.preview(outputs); await controller.confirm(false);
    expect(actions.onPreview).toHaveBeenCalledTimes(1); expect(actions.onConfirm).not.toHaveBeenCalled();
    finish(candidate()); await pending; await controller.preview(outputs);
    expect(actions.onPreview).toHaveBeenCalledTimes(1);
  });

  it('切会话后迟到预览通过旧会话回调释放，不污染新状态', async () => {
    let finish!: (value: GenerationCandidate) => void;
    const old = callbacks(); old.onPreview = vi.fn(() => new Promise<GenerationCandidate>(resolve => { finish = resolve; }));
    const next = callbacks(candidate('乙'));
    const controller = createGenerationController(); controller.start('甲', '甲', old);
    const pending = controller.preview(outputs); controller.start('乙', '乙', next);
    finish(candidate()); await pending;
    expect(old.onCancel).toHaveBeenCalledWith('甲-候选'); expect(next.onCancel).not.toHaveBeenCalled();
    expect(controller.getSnapshot().identity).toBe('乙'); expect(controller.getSnapshot().candidate).toBeNull();
    expect(controller.getSnapshot().error).toBe('');
  });

  it('版本切换及卸载释放当前候选，不重复取消；旧确认失败释放候选', async () => {
    const actions = callbacks();
    const controller = createGenerationController(); controller.start('甲/1', '甲', actions);
    await controller.preview(outputs); controller.start('甲/2', '甲', actions);
    await Promise.resolve(); expect(actions.onCancel).toHaveBeenCalledTimes(1);
    await controller.preview(outputs); controller.stop(); controller.stop();
    await Promise.resolve(); expect(actions.onCancel).toHaveBeenCalledTimes(2);
    let fail!: (reason: Error) => void;
    actions.onConfirm = vi.fn(() => new Promise<void>((_resolve, reject) => { fail = reject; }));
    controller.start('甲/3', '甲', actions); await controller.preview(outputs);
    const confirming = controller.confirm(false); controller.stop();
    expect(actions.onCancel).toHaveBeenCalledTimes(2);
    fail(new Error('旧确认失败')); await confirming;
    expect(actions.onCancel).toHaveBeenCalledTimes(3);
  });

  it('返回会话不匹配时拒绝候选并释放，失败预览不标成功', async () => {
    const actions = callbacks(candidate('其他'));
    const controller = createGenerationController(); controller.start('甲', '甲', actions);
    await controller.preview(outputs);
    expect(controller.getSnapshot().candidate).toBeNull();
    expect(controller.getSnapshot().error).toContain('会话');
    expect(actions.onCancel).toHaveBeenCalledWith('其他-候选');
    vi.mocked(actions.onPreview).mockRejectedValueOnce(new Error('缺少主体贴图'));
    await controller.preview(outputs); expect(controller.getSnapshot().error).toBe('缺少主体贴图');
    expect(controller.getSnapshot().confirmed).toBe(false);
  });

  it('旧确认成功不再取消已消费候选，卸载与进行中的取消共用一次释放', async () => {
    let finish!: () => void;
    const actions = callbacks(); actions.onConfirm = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
    const controller = createGenerationController(); controller.start('甲', '甲', actions);
    await controller.preview(outputs); const confirming = controller.confirm(false);
    controller.stop(); finish(); await confirming;
    expect(actions.onCancel).not.toHaveBeenCalled();
    let finishCancel!: () => void;
    actions.onCancel = vi.fn(() => new Promise<void>(resolve => { finishCancel = resolve; }));
    controller.start('甲/2', '甲', actions); await controller.preview(outputs);
    const cancelling = controller.cancel(); controller.stop();
    await Promise.resolve(); expect(actions.onCancel).toHaveBeenCalledTimes(1);
    finishCancel(); await cancelling;
  });
});
