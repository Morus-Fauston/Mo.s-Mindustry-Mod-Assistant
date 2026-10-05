import { describe, expect, it } from 'vitest';
import { createResourceController } from './controller';

const present = { suffix: '', label: '主体', path: 'sprites/单位.png', exists: true };
const missing = { suffix: '-cell', label: '细胞', path: 'sprites/单位-cell.png', exists: false };

describe('贴图资源确认与会话边界', () => {
  it('替换和删除确认前不执行，取消不改资源，确认只传后缀与确认标志', async () => {
    const calls: unknown[] = [];
    const controller = createResourceController(async () => ({ targets: [present, missing] }), async (action, payload) => { calls.push([action, payload]); });
    await controller.start('工程甲');
    await controller.request('import_sprite', '');
    expect(calls).toEqual([]);
    expect(controller.getSnapshot().confirmation?.action).toBe('import_sprite');
    controller.cancelConfirmation();
    expect(calls).toEqual([]);
    await controller.request('delete_sprite', ''); await controller.confirm();
    expect(calls).toEqual([['delete_sprite', { suffix: '', confirmed: true }]]);
    await controller.request('import_sprite', ''); await controller.confirm();
    expect(calls[1]).toEqual(['import_sprite', { suffix: '', overwrite: true }]);
    await controller.request('import_sprite', '-cell');
    expect(calls[2]).toEqual(['import_sprite', { suffix: '-cell' }]);
  });

  it('原生选择取消正常返回后，依据重读保持原状态而不推断导入成功', async () => {
    let reads = 0;
    const controller = createResourceController(async () => { reads++; return { targets: [missing] }; }, async () => {});
    await controller.start('甲'); await controller.request('import_sprite', '-cell');
    expect(reads).toBe(2);
    expect(controller.getSnapshot().targets[0].exists).toBe(false);
    expect(controller.getSnapshot().error).toBe('');
  });

  it('操作串行且失败保持原目标状态，不显示成功或擅自移除行', async () => {
    let reject!: (reason: Error) => void;
    let calls = 0;
    const controller = createResourceController(async () => ({ targets: [present] }), async () => {
      calls++; return new Promise<void>((_resolve, fail) => { reject = fail; });
    });
    await controller.start('甲');
    const operation = controller.request('reveal_sprite', '');
    await controller.request('reveal_sprite', ''); expect(calls).toBe(1);
    reject(new Error('目标不可访问')); await operation;
    expect(controller.getSnapshot().error).toBe('目标不可访问');
    expect(controller.getSnapshot().targets).toEqual([present]);
    expect(controller.getSnapshot().pending).toBeNull();
  });

  it('切文档后迟到读取和旧确认不能进入新文档', async () => {
    let finish!: (result: { targets: typeof present[] }) => void;
    let reads = 0, calls = 0;
    const controller = createResourceController(() => ++reads === 1 ? new Promise(resolve => { finish = resolve; })
      : Promise.resolve({ targets: [missing] }), async () => { calls++; });
    const old = controller.start('甲'); await controller.start('乙');
    finish({ targets: [present] }); await old;
    expect(controller.getSnapshot().identity).toBe('乙');
    expect(controller.getSnapshot().targets).toEqual([missing]);
    await controller.confirm(); expect(calls).toBe(0);
  });

  it('版本变化使旧确认失效，卸载后迟到失败不会刷新或通知', async () => {
    let reject!: (reason: Error) => void;
    let calls = 0, reads = 0, notices = 0;
    const controller = createResourceController(async () => { reads++; return { targets: [present] }; }, async () => {
      calls++; return new Promise<void>((_resolve, fail) => { reject = fail; });
    });
    controller.subscribe(() => { notices++; });
    await controller.start('甲:1'); await controller.request('delete_sprite', '');
    await controller.start('甲:2'); await controller.confirm(); expect(calls).toBe(0);
    const pending = controller.request('reveal_sprite', '');
    controller.stop(); const previous = notices;
    reject(new Error('旧会话失败')); await pending;
    expect(notices).toBe(previous); expect(reads).toBe(2);
  });
});
