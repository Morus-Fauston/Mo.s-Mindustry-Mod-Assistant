import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { ContentTools } from './ContentTools';

describe('内容工具首次渲染', () => {
  it('无工程时提供新建工程入口，真实内容操作保持禁用且不自动读写', () => {
    const loadCatalogue = vi.fn(), onAction = vi.fn();
    const html = renderToStaticMarkup(createElement(ContentTools, {
      sessionId: null, activePath: null, disabled: false, loadCatalogue, onAction,
    }));
    expect(html).toMatch(/<button[^>]*>新建工程<\/button>/);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>新建内容<\/button>/);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>重命名<\/button>/);
    expect(html).not.toContain('<dialog');
    expect(loadCatalogue).not.toHaveBeenCalled();
    expect(onAction).not.toHaveBeenCalled();
  });

  it('活动内容操作跟随调用方禁用态，不替用户启动定位', () => {
    const onAction = vi.fn();
    const html = renderToStaticMarkup(createElement(ContentTools, {
      sessionId: 's', activePath: 'content/units/same.json', disabled: true,
      loadCatalogue: vi.fn(), onAction,
    }));
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>定位文件<\/button>/);
    expect(onAction).not.toHaveBeenCalled();
  });
});
