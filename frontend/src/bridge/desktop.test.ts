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

describe('工程请求桥接', () => {
  afterEach(() => vi.useRealTimers());
  const makeHost = (request: (envelope: any) => Promise<unknown>) => {
    const host = new EventTarget() as DesktopHost;
    host.pywebview = { api: { bootstrap: async () => summary, request } };
    return host;
  };
  const reply = (envelope: any, data: unknown = { name: '资料' }) => ({
    ok: true, protocolVersion: 1, requestId: envelope.requestId,
    sessionId: envelope.sessionId, data,
  });

  it('等待request真实就绪，传递唯一请求身份', async () => {
    const host = new EventTarget() as DesktopHost;
    const client = createDesktopClient(host);
    const result = client.request('recent_projects', {}, null);
    const request = vi.fn(async envelope => reply(envelope, { recentProjects: [] }));
    host.pywebview = { api: { bootstrap: async () => summary, request } };
    host.dispatchEvent(new Event('pywebviewready'));
    expect(await result).toEqual({ recentProjects: [] });
    expect(request.mock.calls[0][0]).toMatchObject({ protocolVersion: 1, action: 'recent_projects', payload: {}, sessionId: null });
    expect(request.mock.calls[0][0].requestId).toMatch(/^[0-9a-f-]{36}$/);
  });

  it('相同请求ID合并，冲突内容拒绝；完成后可原ID手动重试', async () => {
    let finish!: (data: unknown) => void;
    const request = vi.fn(envelope => new Promise(resolve => { finish = () => resolve(reply(envelope)); }));
    const client = createDesktopClient(makeHost(request));
    const first = client.request('read_document', { path: 'content/units/a.json' }, 'a', 'same');
    expect(client.request('read_document', { path: 'content/units/a.json' }, 'a', 'same')).toBe(first);
    await expect(client.request('read_document', { path: 'content/units/b.json' }, 'a', 'same')).rejects.toMatchObject({ code: 'REQUEST_ID_CONFLICT' });
    await Promise.resolve(); await Promise.resolve();
    finish(null);
    await first;
    expect(request).toHaveBeenCalledTimes(1);
    request.mockImplementation(async envelope => reply(envelope));
    await client.request('read_document', { path: 'content/units/a.json' }, 'a', 'same');
    expect(request).toHaveBeenCalledTimes(2);
  });

  it.each([
    (e: any) => ({ ...reply(e), requestId: 'wrong' }),
    (e: any) => ({ ...reply(e), protocolVersion: 2 }),
    (e: any) => ({ ...reply(e), ok: 'yes' }),
    () => null,
  ])('拒绝错误请求身份、协议或损坏的响应', async mutate => {
    const client = createDesktopClient(makeHost(async e => mutate(e)));
    await expect(client.request('recent_projects', {}, null)).rejects.toBeInstanceOf(Error);
  });

  it('读取响应不可跨会话；打开工程可进入新会话', async () => {
    const client = createDesktopClient(makeHost(async e => ({ ...reply(e, { sessionId: 'b' }), sessionId: 'b' })));
    await expect(client.request('read_document', {}, 'a')).rejects.toMatchObject({ code: 'STALE_SESSION' });
    expect(await client.request('open_project', { path: 'D:/mod' }, 'a')).toEqual({ sessionId: 'b' });
  });

  it('新工程打开后迟到的旧读取不得返回成功', async () => {
    let finish!: () => void;
    const client = createDesktopClient(makeHost(e => e.action === 'read_document'
      ? new Promise(resolve => { finish = () => resolve(reply(e)); })
      : Promise.resolve({ ...reply(e, { sessionId: 'b' }), sessionId: 'b' })));
    const old = client.request('read_document', {}, 'a');
    const rejected = expect(old).rejects.toMatchObject({ code: 'STALE_SESSION' });
    await client.request('open_project', {}, 'a');
    finish();
    await rejected;
  });

  it('读取15秒超时，迟到结果无效且不自动重放', async () => {
    vi.useFakeTimers();
    let finish!: () => void;
    const request = vi.fn(e => new Promise(resolve => { finish = () => resolve(reply(e)); }));
    const client = createDesktopClient(makeHost(request));
    const failed = expect(client.request('read_document', {}, 'a')).rejects.toMatchObject({ code: 'BRIDGE_TIMEOUT' });
    await vi.advanceTimersByTimeAsync(15_000);
    await failed;
    finish();
    await Promise.resolve();
    expect(request).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('选择目录最多等待300秒并保留取消结果', async () => {
    vi.useFakeTimers();
    let finish!: () => void;
    const client = createDesktopClient(makeHost(e => new Promise(resolve => { finish = () => resolve(reply(e, { cancelled: true })); })));
    const pending = client.request('choose_project', {}, 'a');
    await vi.advanceTimersByTimeAsync(299_999);
    finish();
    expect(await pending).toEqual({ cancelled: true });
    const failed = expect(client.request('choose_project', {}, 'a')).rejects.toMatchObject({ code: 'BRIDGE_TIMEOUT' });
    await vi.advanceTimersByTimeAsync(300_000);
    await failed;
  });

  it('最多32个并发请求，失败后释放容量', async () => {
    vi.useFakeTimers();
    const client = createDesktopClient(makeHost(() => new Promise(() => {})));
    const pending = Array.from({ length: 32 }, () => client.request('recent_projects', {}, null).catch(e => e.code));
    await expect(client.request('recent_projects', {}, null)).rejects.toMatchObject({ code: 'BRIDGE_BUSY' });
    await vi.advanceTimersByTimeAsync(15_000);
    expect(await Promise.all(pending)).toEqual(Array(32).fill('BRIDGE_TIMEOUT'));
    const retry = expect(client.request('recent_projects', {}, null)).rejects.toMatchObject({ code: 'BRIDGE_TIMEOUT' });
    await vi.advanceTimersByTimeAsync(15_000);
    await retry;
  });

  it('宿主结构化失败保留中文消息及文件定位，调用异常不泄露原生堆栈', async () => {
    const request = vi.fn(async e => ({ ...reply(e), ok: false,
      error: { code: 'INVALID_DOCUMENT', message: '内容文件损坏。', path: 'content/units/a.json' },
    }));
    const host = makeHost(request);
    const client = createDesktopClient(host);
    await expect(client.request('read_document', {}, 'a')).rejects.toMatchObject({
      code: 'INVALID_DOCUMENT', message: '内容文件损坏。', path: 'content/units/a.json',
    });
    host.pywebview!.api!.request = () => { throw new Error('native stack'); };
    await expect(client.request('read_document', {}, 'a')).rejects.toMatchObject({
      code: 'BRIDGE_FAILURE', message: '桌面操作失败，请稍后重试。',
    });
  });

  it('仅bootstrap存在不能视为request就绪；等待结束后移除监听并可重试', async () => {
    vi.useFakeTimers();
    const host = new EventTarget() as DesktopHost;
    host.pywebview = { api: { bootstrap: async () => summary } };
    const client = createDesktopClient(host);
    const rejected = expect(client.request('recent_projects', {}, null)).rejects.toMatchObject({ code: 'BRIDGE_UNAVAILABLE' });
    host.dispatchEvent(new Event('pywebviewready'));
    await vi.advanceTimersByTimeAsync(8000);
    await rejected;
    const request = vi.fn(async e => reply(e, { recentProjects: [] }));
    host.pywebview.api!.request = request;
    host.dispatchEvent(new Event('pywebviewready'));
    await Promise.resolve();
    expect(request).not.toHaveBeenCalled();
    expect(await client.request('recent_projects', {}, null)).toEqual({ recentProjects: [] });
    expect(vi.getTimerCount()).toBe(0);
  });

  it('打开超时后只查询原结果，恢复新会话并隔离旧读取', async () => {
    vi.useFakeTimers();
    let openEnvelope: any;
    let finishRead!: () => void;
    const request = vi.fn(e => {
      if (e.action === 'open_project') { openEnvelope = e; return new Promise(() => {}); }
      return new Promise(resolve => { finishRead = () => resolve(reply(e)); });
    });
    const host = makeHost(request);
    const client = createDesktopClient(host);
    const timedOut = expect(client.request('open_project', { path: 'D:/mod' }, 'a', 'open-id'))
      .rejects.toMatchObject({ code: 'BRIDGE_TIMEOUT' });
    await vi.advanceTimersByTimeAsync(15_000);
    await timedOut;
    const old = client.request('read_document', {}, 'a');
    const stale = expect(old).rejects.toMatchObject({ code: 'STALE_SESSION' });
    const query = vi.fn(async () => ({ state: 'completed', response: {
      ...reply(openEnvelope, { sessionId: 'b', name: '新工程' }), sessionId: 'b',
    } }));
    host.pywebview!.api!.request_result = query;
    expect(await client.recoverRequest('open_project', { path: 'D:/mod' }, 'a', 'open-id'))
      .toEqual({ sessionId: 'b', name: '新工程' });
    finishRead();
    await stale;
    expect(query).toHaveBeenCalledWith('open-id');
    expect(request.mock.calls.filter(([e]) => e.action === 'open_project')).toHaveLength(1);
  });

  it.each([['pending', 'REQUEST_PENDING'], ['unknown', 'REQUEST_UNKNOWN']])(
    '查询状态%s时给出明确错误而不重放操作', async (state, code) => {
      const request = vi.fn(async e => reply(e));
      const host = makeHost(request);
      host.pywebview!.api!.request_result = vi.fn(async () => ({ state }));
      const client = createDesktopClient(host);
      await expect(client.recoverRequest('choose_project', {}, 'a', 'original')).rejects.toMatchObject({ code });
      expect(request).not.toHaveBeenCalled();
    },
  );

  it('查询原选择目录结果也只等待15秒，迟到结果不切换会话', async () => {
    vi.useFakeTimers();
    const request = vi.fn(async e => reply(e));
    const host = makeHost(request);
    let finish!: (value: unknown) => void;
    host.pywebview!.api!.request_result = () => new Promise(resolve => { finish = resolve; });
    const client = createDesktopClient(host);
    const timedOut = expect(client.recoverRequest('choose_project', {}, 'a', 'original'))
      .rejects.toMatchObject({ code: 'BRIDGE_TIMEOUT' });
    await vi.advanceTimersByTimeAsync(15_000);
    await timedOut;
    finish({ state: 'completed', response: {
      ok: true, protocolVersion: 1, requestId: 'original', sessionId: 'b', data: { sessionId: 'b' },
    } });
    await Promise.resolve();
    expect(request).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each([null, { state: 'invalid' }, { state: 'completed' }, {
    state: 'completed', response: { ok: true, protocolVersion: 1, requestId: 'wrong', sessionId: 'b', data: { sessionId: 'b' } },
  }])('查询结果仍须验证格式和原请求身份', async result => {
    const request = vi.fn(async e => reply(e));
    const host = makeHost(request);
    host.pywebview!.api!.request_result = async () => result;
    await expect(createDesktopClient(host).recoverRequest('open_project', {}, 'a', 'original'))
      .rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
    expect(request).not.toHaveBeenCalled();
  });
});
