import { afterEach, describe, expect, it, vi } from 'vitest';
import { createDesktopClient, type DesktopHost } from './desktop';

const summary = {
  ok: true as const, protocolVersion: 1,
  data: { metadata: { gameVersion: '159', classCount: 2, categories: [] } },
};

describe('桌面启动桥接', () => {
  afterEach(() => vi.useRealTimers());

  it('等待真实宿主就绪，合并同时发生的读取', async () => {
    const host = new EventTarget() as DesktopHost;
    const client = createDesktopClient(host);
    const first = client.bootstrap();
    const second = client.bootstrap();
    const bootstrap = vi.fn(async () => summary);
    host.pywebview = { api: { bootstrap } };
    host.dispatchEvent(new Event('pywebviewready'));
    expect(await first).toEqual(summary.data);
    expect(await second).toEqual(summary.data);
    expect(bootstrap).toHaveBeenCalledTimes(1);
    expect(bootstrap).toHaveBeenCalledWith(1);
  });

  it('宿主不可达时给出错误，不切换为演示数据；稍后可手动重试', async () => {
    vi.useFakeTimers();
    const host = new EventTarget() as DesktopHost;
    const client = createDesktopClient(host);
    const failure = expect(client.bootstrap()).rejects.toThrow('请从桌面程序启动');
    await vi.advanceTimersByTimeAsync(8000);
    await failure;
    host.pywebview = { api: { bootstrap: async () => summary } };
    expect(await client.bootstrap()).toEqual(summary.data);
  });

  it('协议不匹配时禁止进入编辑界面', async () => {
    const host = new EventTarget() as DesktopHost;
    host.pywebview = { api: { bootstrap: async () => ({ ...summary, protocolVersion: 2 }) } };
    await expect(createDesktopClient(host).bootstrap()).rejects.toThrow('版本不匹配');
  });

  it('元数据失败保留宿主错误，恢复后能重新读取', async () => {
    const host = new EventTarget() as DesktopHost;
    const bootstrap = vi.fn().mockResolvedValueOnce({
      ok: false, protocolVersion: 1,
      error: { code: 'METADATA_UNAVAILABLE', message: '无法读取离线元数据，请检查程序资料是否完整后重试。' },
    }).mockResolvedValueOnce(summary);
    host.pywebview = { api: { bootstrap } };
    const client = createDesktopClient(host);
    await expect(client.bootstrap()).rejects.toMatchObject({
      code: 'METADATA_UNAVAILABLE', message: '无法读取离线元数据，请检查程序资料是否完整后重试。',
    });
    expect(await client.bootstrap()).toEqual(summary.data);
  });

  it('宿主无响应时有限等待，旧响应不能覆盖重试结果', async () => {
    vi.useFakeTimers();
    let finishOld!: (value: unknown) => void;
    const host = new EventTarget() as DesktopHost;
    const bootstrap = vi.fn()
      .mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve; }))
      .mockResolvedValueOnce(summary);
    host.pywebview = { api: { bootstrap } };
    const client = createDesktopClient(host);
    const first = client.bootstrap();
    const failure = expect(first).rejects.toMatchObject({ code: 'BRIDGE_TIMEOUT' });
    await vi.advanceTimersByTimeAsync(8000);
    await failure;
    expect(await client.bootstrap()).toEqual(summary.data);
    finishOld({ ...summary, data: { metadata: { ...summary.data.metadata, gameVersion: '旧版本' } } });
    await Promise.resolve();
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each([
    null,
    { ok: true, protocolVersion: 1 },
    { ...summary, data: { metadata: { ...summary.data.metadata, classCount: -1 } } },
    { ...summary, data: { metadata: { ...summary.data.metadata, categories: [{ name: 'Units', count: '2' }] } } },
    { ok: false, protocolVersion: 1, error: null },
  ])('损坏的宿主响应不能进入就绪状态（%j）', async response => {
    const host = new EventTarget() as DesktopHost;
    host.pywebview = { api: { bootstrap: async () => response } };
    await expect(createDesktopClient(host).bootstrap()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });

  it.each([
    () => { throw new Error('native stack trace'); },
    () => Promise.reject('native bridge error'),
  ])('桥接异常转为中文错误并释放本次请求', async bootstrap => {
    vi.useFakeTimers();
    const host = new EventTarget() as DesktopHost;
    host.pywebview = { api: { bootstrap } };
    const client = createDesktopClient(host);
    await expect(client.bootstrap()).rejects.toMatchObject({
      code: 'BRIDGE_FAILURE', message: '读取桌面程序资料失败，请稍后重试。',
    });
    expect(vi.getTimerCount()).toBe(0);
    host.pywebview = { api: { bootstrap: async () => summary } };
    expect(await client.bootstrap()).toEqual(summary.data);
  });
});
