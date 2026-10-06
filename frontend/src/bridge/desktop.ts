const PROTOCOL_VERSION = 1;
const TIMEOUT_MS = 8000;

export interface BootstrapData {
  application: { version: string };
  metadata: {
    gameVersion: string;
    classCount: number;
    categories: { name: string; count: number }[];
  };
}

interface DesktopApi {
  bootstrap(protocolVersion: number): Promise<unknown>;
  request?(envelope: RequestEnvelope): Promise<unknown>;
  request_result?(requestId: string): Promise<unknown>;
}

interface RequestEnvelope {
  protocolVersion: number;
  requestId: string;
  sessionId: string | null;
  action: string;
  payload: Record<string, unknown>;
}

export interface DesktopHost extends EventTarget {
  pywebview?: { api?: DesktopApi };
}

export class DesktopError extends Error {
  constructor(readonly code: string, message: string, readonly path?: string) {
    super(message);
    this.name = 'DesktopError';
  }
}

/** Only these command results may adopt another session without resetting its history. */
export function workspaceTransitionSession(action: string, data: unknown): string | undefined {
  if (!['create_project', 'close_project', 'undo', 'redo'].includes(action)) return undefined;
  const invalid = () => new DesktopError('INVALID_RESPONSE', '工程转换资料无效，请查询原操作结果。');
  if (!record(data)) throw invalid();
  if (!Object.hasOwn(data, 'project')) {
    if (action === 'close_project' || action === 'create_project' && data.cancelled !== true) throw invalid();
    return undefined;
  }
  const state = action === 'create_project' || action === 'close_project' ? data.state : data;
  if (!record(state) || typeof state.sessionId !== 'string' || !state.sessionId || !count(state.revision)
      || !Array.isArray(state.documents) || !record(state.history) || !count(state.autoSaveInterval)
      || typeof state.history.canUndo !== 'boolean' || typeof state.history.canRedo !== 'boolean'
      || typeof state.history.undoDescription !== 'string' || typeof state.history.redoDescription !== 'string'
      || state.documents.some(document => !record(document) || document.sessionId !== state.sessionId)) throw invalid();
  if (action === 'close_project' && (data.project !== null || state.documents.length !== 0
      || state.history.canUndo || state.history.canRedo || state.history.undoDescription || state.history.redoDescription)) throw invalid();
  if (data.project === null) {
    if (action === 'create_project' || data.cancelled === true) throw invalid();
  } else if (!record(data.project) || data.project.sessionId !== state.sessionId
      || typeof data.project.name !== 'string' || typeof data.project.root !== 'string' || !data.project.root
      || !Array.isArray(data.project.tree) || data.cancelled === true) throw invalid();
  return state.sessionId;
}

function readRequest(api: DesktopApi, envelope: RequestEnvelope, recover: boolean): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new DesktopError(
      'BRIDGE_TIMEOUT', '桌面程序响应超时，请稍后重试。',
    )), !recover && envelope.action === 'choose_project' ? 300_000 : 15_000);
    Promise.resolve().then(() => recover ? api.request_result!(envelope.requestId) : api.request!(envelope)).then(
      response => { clearTimeout(timer); resolve(response); },
      () => {
        clearTimeout(timer);
        reject(new DesktopError('BRIDGE_FAILURE', '桌面操作失败，请稍后重试。'));
      },
    );
  });
}

function parseRequest(response: unknown, envelope: RequestEnvelope): { data: unknown; opened: boolean } {
  const invalid = () => new DesktopError('INVALID_RESPONSE', '桌面程序返回的资料格式不正确，请重启后重试。');
  if (!record(response) || response.requestId !== envelope.requestId ||
      typeof response.protocolVersion !== 'number') throw invalid();
  if (response.protocolVersion !== PROTOCOL_VERSION) {
    throw new DesktopError('PROTOCOL_MISMATCH', '界面与程序版本不匹配，请使用同一发行包。');
  }
  if (response.sessionId !== null && typeof response.sessionId !== 'string') throw invalid();
  if (response.ok === false) {
    if (!record(response.error) || typeof response.error.code !== 'string' ||
        typeof response.error.message !== 'string' || !response.error.message.trim()) throw invalid();
    throw new DesktopError(response.error.code, response.error.message,
      typeof response.error.path === 'string' ? response.error.path : undefined);
  }
  if (response.ok !== true || !record(response.data)) throw invalid();
  const transition = workspaceTransitionSession(envelope.action, response.data);
  if (transition !== undefined && transition !== response.sessionId) throw invalid();
  const opening = envelope.action === 'open_project' || envelope.action === 'choose_project';
  const opened = opening && response.data.cancelled !== true;
  if (opened) {
    if (typeof response.sessionId !== 'string' || !response.sessionId ||
        response.data.sessionId !== response.sessionId) throw invalid();
  } else if (transition === undefined && envelope.action !== 'recent_projects' && response.sessionId !== envelope.sessionId) {
    throw new DesktopError('STALE_SESSION', '工程已切换，请重新打开所需内容。');
  }
  if ('sessionId' in response.data && response.data.sessionId !== response.sessionId) throw invalid();
  if ('state' in response.data && (!record(response.data.state) || response.data.state.sessionId !== response.sessionId)) throw invalid();
  return { data: response.data, opened: opened || transition !== undefined && transition !== envelope.sessionId };
}

function readBootstrap(api: DesktopApi): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new DesktopError('BRIDGE_TIMEOUT', '桌面程序响应超时，请稍后重试。'));
    }, TIMEOUT_MS);
    Promise.resolve().then(() => api.bootstrap(PROTOCOL_VERSION)).then(
      response => { clearTimeout(timer); resolve(response); },
      () => {
        clearTimeout(timer);
        reject(new DesktopError('BRIDGE_FAILURE', '读取桌面程序资料失败，请稍后重试。'));
      },
    );
  });
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function count(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

function parseBootstrap(response: unknown): BootstrapData {
  const invalid = () => new DesktopError('INVALID_RESPONSE', '桌面程序返回的资料格式不正确，请重启后重试。');
  if (!record(response) || typeof response.protocolVersion !== 'number') throw invalid();
  if (response.protocolVersion !== PROTOCOL_VERSION) {
    throw new DesktopError('PROTOCOL_MISMATCH', '界面与程序版本不匹配，请使用同一发行包。');
  }
  if (response.ok === false) {
    if (!record(response.error) || typeof response.error.code !== 'string' ||
        typeof response.error.message !== 'string' || !response.error.message.trim()) throw invalid();
    throw new DesktopError(response.error.code, response.error.message);
  }
  if (response.ok !== true || !record(response.data) || !record(response.data.metadata)) throw invalid();
  const metadata = response.data.metadata;
  const application = response.data.application;
  if (!record(application) || typeof application.version !== 'string' || !application.version.trim()) throw invalid();
  if (typeof metadata.gameVersion !== 'string' || !count(metadata.classCount) ||
      !Array.isArray(metadata.categories)) throw invalid();
  const categories = metadata.categories.map(category => {
    if (!record(category) || typeof category.name !== 'string' || !count(category.count)) throw invalid();
    return { name: category.name, count: category.count };
  });
  return { application: { version: application.version }, metadata: { gameVersion: metadata.gameVersion, classCount: metadata.classCount, categories } };
}

export function createDesktopClient(host: DesktopHost) {
  let pending: Promise<BootstrapData> | undefined;
  let sessionRevision = 0;
  const requests = new Map<string, { signature: string; promise: Promise<unknown> }>();

  function ready(method: keyof DesktopApi = 'bootstrap'): Promise<DesktopApi> {
    if (typeof host.pywebview?.api?.[method] === 'function') {
      return Promise.resolve(host.pywebview.api);
    }
    return new Promise((resolve, reject) => {
      const finish = () => {
        if (typeof host.pywebview?.api?.[method] !== 'function') return;
        clearTimeout(timer);
        host.removeEventListener('pywebviewready', finish);
        resolve(host.pywebview.api);
      };
      const timer = setTimeout(() => {
        host.removeEventListener('pywebviewready', finish);
        reject(new DesktopError('BRIDGE_UNAVAILABLE', '无法连接桌面程序，请从桌面程序启动后重试。'));
      }, TIMEOUT_MS);
      host.addEventListener('pywebviewready', finish);
      finish();
    });
  }

  function dispatch<T>(action: string, payload: Record<string, unknown>, sessionId: string | null,
      requestId: string, recover: boolean): Promise<T> {
      if (!action.trim() || !requestId.trim() || requestId.length > 128 ||
          (sessionId !== null && typeof sessionId !== 'string') || !record(payload)) {
        return Promise.reject(new DesktopError('INVALID_REQUEST', '桌面请求参数不正确。'));
      }
      let signature: string;
      let snapshot: Record<string, unknown>;
      try {
        signature = JSON.stringify({ action, payload, sessionId });
        snapshot = JSON.parse(signature).payload;
      } catch {
        return Promise.reject(new DesktopError('INVALID_REQUEST', '桌面请求必须使用可序列化的资料。'));
      }
      const key = `${recover ? 'result' : 'request'}:${requestId}`;
      const existing = requests.get(key);
      if (existing) {
        return existing.signature === signature ? existing.promise as Promise<T>
          : Promise.reject(new DesktopError('REQUEST_ID_CONFLICT', '请求编号已用于其他操作，请重新发起。'));
      }
      if (requests.size >= 32) {
        return Promise.reject(new DesktopError('BRIDGE_BUSY', '桌面程序正在处理较多请求，请稍后重试。'));
      }
      const revision = sessionRevision;
      const envelope: RequestEnvelope = { protocolVersion: PROTOCOL_VERSION, requestId, action, payload: snapshot, sessionId };
      const promise = ready(recover ? 'request_result' : 'request').then(api => readRequest(api, envelope, recover)).then(response => {
        if (revision !== sessionRevision && action !== 'recent_projects') {
          throw new DesktopError('STALE_SESSION', '工程已切换，请重新打开所需内容。');
        }
        if (recover) {
          if (!record(response)) throw new DesktopError('INVALID_RESPONSE', '桌面程序返回的操作状态格式不正确。');
          if (response.state === 'pending') throw new DesktopError('REQUEST_PENDING', '原操作仍在处理中，请稍后查询结果。');
          if (response.state === 'unknown') throw new DesktopError('REQUEST_UNKNOWN', '无法确认原操作结果，请重新启动程序后打开工程。');
          if (response.state !== 'completed') throw new DesktopError('INVALID_RESPONSE', '桌面程序返回的操作状态格式不正确。');
          response = response.response;
        }
        const parsed = parseRequest(response, envelope);
        if (parsed.opened) sessionRevision += 1;
        return parsed.data as T;
      }).finally(() => { requests.delete(key); });
      requests.set(key, { signature, promise });
      return promise;
  }

  return {
    request<T>(action: string, payload: Record<string, unknown>, sessionId: string | null,
      requestId: string = crypto.randomUUID()): Promise<T> {
      return dispatch<T>(action, payload, sessionId, requestId, false);
    },
    recoverRequest<T>(action: string, payload: Record<string, unknown>, sessionId: string | null,
      requestId: string): Promise<T> {
      return dispatch<T>(action, payload, sessionId, requestId, true);
    },
    bootstrap(): Promise<BootstrapData> {
      if (!pending) {
        pending = ready().then(readBootstrap).then(parseBootstrap)
          .finally(() => { pending = undefined; });
      }
      return pending;
    },
  };
}

export const desktop = createDesktopClient(
  typeof window === 'undefined' ? new EventTarget() : window,
);
