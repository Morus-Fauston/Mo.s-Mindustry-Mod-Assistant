import type { PreviewLayer, PreviewResource } from './types';

const MAX_SCENE_PIXELS = 16 * 1024 * 1024;

/** Reserve before starting an asynchronous decode, shared by all scene workers. */
export function createDecodeBudget(layers: Pick<PreviewLayer, 'resourceId' | 'width' | 'height'>[]): (resource: PreviewResource) => void {
  const reserved = new Set<string>();
  let pixels = 0;
  return resource => {
    const declared = layers.filter(layer => layer.resourceId === resource.resourceId);
    if (!declared.length || declared.some(layer => layer.width !== resource.width || layer.height !== resource.height)) {
      throw new Error('贴图尺寸与场景声明不一致，已跳过该资源。');
    }
    if (reserved.has(resource.resourceId)) return;
    const cost = resource.width * resource.height;
    if (!Number.isSafeInteger(cost) || cost <= 0 || pixels + cost > MAX_SCENE_PIXELS) {
      throw new Error('预览贴图总像素超过限制，已跳过超额资源。');
    }
    pixels += cost;
    reserved.add(resource.resourceId);
  };
}

/** Only the Python resource endpoint may supply PNGs; never assign arbitrary URLs. */
export function validateResource(resource: PreviewResource, sessionId: string, resourceId: string): void {
  if (!resource || typeof resource !== 'object') throw new Error('贴图资料格式不正确。');
  if (resource.sessionId !== sessionId || resource.resourceId !== resourceId) {
    throw new Error('贴图所属工程已改变，请重新载入预览。');
  }
  if (resource.mime !== 'image/png' || typeof resource.dataUrl !== 'string' ||
      !resource.dataUrl.startsWith('data:image/png;base64,iVBORw0KGgo') || resource.dataUrl.length > 48 * 1024 * 1024 ||
      !Number.isSafeInteger(resource.width) || !Number.isSafeInteger(resource.height) ||
      resource.width <= 0 || resource.height <= 0 || resource.width * resource.height > 32 * 1024 * 1024) {
    throw new Error('贴图格式或尺寸不受支持。');
  }
}

export function decodePng(resource: PreviewResource, signal: AbortSignal): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const clear = () => {
      clearTimeout(timer);
      image.onload = null; image.onerror = null;
      signal.removeEventListener('abort', abort);
    };
    const fail = (message: string) => { clear(); image.src = ''; reject(new Error(message)); };
    const abort = () => fail('预览读取已取消。');
    const timer = setTimeout(() => fail('贴图解码超时，请重新载入。'), 15_000);
    image.onload = () => {
      if (image.naturalWidth !== resource.width || image.naturalHeight !== resource.height) {
        fail('贴图尺寸与资源记录不一致。');
      } else { clear(); resolve(image); }
    };
    image.onerror = () => fail('贴图损坏，无法解码。');
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) { abort(); return; }
    image.src = resource.dataUrl;
  });
}
