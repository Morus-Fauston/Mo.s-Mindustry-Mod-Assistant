import { describe, expect, it } from 'vitest';
import { validateResource, createDecodeBudget } from './resources';
import type { PreviewLayer, PreviewResource } from './types';

const png: PreviewResource = {
  sessionId: 'current', resourceId: 'checked-png', mime: 'image/png', width: 1, height: 1,
  dataUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==',
};

describe('受控预览资源', () => {
  it('仅接受当前工程、匹配资源身份且含PNG文件头的数据', () => {
    expect(() => validateResource(png, 'current', 'checked-png')).not.toThrow();
    expect(() => validateResource(png, 'old', 'checked-png')).toThrow('工程');
    expect(() => validateResource(png, 'current', 'different')).toThrow('工程');
    expect(() => validateResource({ ...png, dataUrl: 'https://example.com/image.png' }, 'current', 'checked-png')).toThrow('格式');
    expect(() => validateResource({ ...png, dataUrl: 'data:image/png;base64,PHN2Zy8+' }, 'current', 'checked-png')).toThrow('格式');
    expect(() => validateResource({ ...png, width: 1e9 }, 'current', 'checked-png')).toThrow('尺寸');
  });

  it('同步预留累计唯一像素，两个8M资源耗尽预算，重复镜像不重复计费', () => {
    const layers: PreviewLayer[] = ['a', 'b', 'c'].map(id => ({
      key: id, resourceId: id, x: 0, y: 0, z: 0, width: 4096, height: 2048, flipX: false, tooltip: '',
    }));
    layers.push({ ...layers[0], key: 'mirror', flipX: true });
    const reserve = createDecodeBudget(layers);
    const resource = (id: string) => ({ ...png, resourceId: id, width: 4096, height: 2048 });
    expect(() => reserve(resource('a'))).not.toThrow();
    expect(() => reserve(resource('a'))).not.toThrow();
    expect(() => reserve(resource('b'))).not.toThrow();
    expect(() => reserve(resource('c'))).toThrow('预览贴图总像素超过限制');
    expect(() => createDecodeBudget(layers)(resource('c'))).not.toThrow();
  });

  it('资源尺寸不匹配任一场景声明时拒绝，失败不占预算', () => {
    const layers: PreviewLayer[] = [
      { key: 'a', resourceId: 'a', x: 0, y: 0, z: 0, width: 4096, height: 4096, flipX: false, tooltip: '' },
      { key: 'b', resourceId: 'b', x: 0, y: 0, z: 0, width: 4096, height: 4096, flipX: false, tooltip: '' },
    ];
    const reserve = createDecodeBudget(layers);
    expect(() => reserve({ ...png, resourceId: 'a', width: 4096, height: 4000 })).toThrow('场景声明');
    expect(() => reserve({ ...png, resourceId: 'b', width: 4096, height: 4096 })).not.toThrow();
    const conflicting = createDecodeBudget([layers[0], { ...layers[0], key: 'mirror', width: 1 }]);
    expect(() => conflicting({ ...png, resourceId: 'a', width: 4096, height: 4096 })).toThrow('场景声明');
  });
});
