const PROTOCOL_VERSION = 1;
const TIMEOUT_MS = 8000;

export interface BootstrapData {
  metadata: {
    gameVersion: string;
    classCount: number;
    categories: { name: string; count: number }[];
  };
}

interface DesktopApi {
  bootstrap(protocolVersion: number): Promise<unknown>;
}

export interface DesktopHost extends EventTarget {
  pywebview?: { api?: DesktopApi };
}

export class DesktopError extends Error {
  constructor(readonly code: string, message: string) {
    super(message);
    this.name = 'DesktopError';
  }
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
  if (typeof metadata.gameVersion !== 'string' || !count(metadata.classCount) ||
      !Array.isArray(metadata.categories)) throw invalid();
  const categories = metadata.categories.map(category => {
    if (!record(category) || typeof category.name !== 'string' || !count(category.count)) throw invalid();
    return { name: category.name, count: category.count };
  });
  return { metadata: { gameVersion: metadata.gameVersion, classCount: metadata.classCount, categories } };
}

export function createDesktopClient(host: DesktopHost) {
  let pending: Promise<BootstrapData> | undefined;

  function ready(): Promise<DesktopApi> {
    if (typeof host.pywebview?.api?.bootstrap === 'function') {
      return Promise.resolve(host.pywebview.api);
    }
    return new Promise((resolve, reject) => {
      const finish = () => {
        if (typeof host.pywebview?.api?.bootstrap !== 'function') return;
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

  return {
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
