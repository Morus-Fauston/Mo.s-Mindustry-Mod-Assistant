import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { WorkbenchLayout } from './WorkbenchLayout';
import { Separator } from './Separator';

describe('受控三栏与可访问分隔线结构', () => {
  it('隐藏面板仍渲染真实子树且不发送布局写入，中央编辑器一直挂载', () => {
    const onLayoutChange = vi.fn();
    const html = renderToStaticMarkup(createElement(WorkbenchLayout, {
      layout: { leftWidth: 230, rightWidth: 380, previewRatio: .6, filesVisible: false, previewVisible: false },
      onLayoutChange, files: createElement('input', { defaultValue: '未提交搜索' }),
      editor: createElement('textarea', { defaultValue: '未提交源码' }), preview: createElement('div', null, '已有预览状态'),
    }));
    expect(html).toContain('未提交搜索'); expect(html).toContain('未提交源码'); expect(html).toContain('已有预览状态');
    expect(html.match(/hidden=""/g)).toHaveLength(2);
    expect(html).not.toContain('role="separator"');
    expect(onLayoutChange).not.toHaveBeenCalled();
  });
  it('可见侧栏各有独立命名的分隔线，初次未测量时不允许非法拖动', () => {
    const html = renderToStaticMarkup(createElement(WorkbenchLayout, {
      layout: { leftWidth: null, rightWidth: null, previewRatio: null, filesVisible: true, previewVisible: true },
      onLayoutChange: () => {}, files: '文件', editor: '编辑', preview: '预览',
    }));
    expect(html.match(/role="separator"/g)).toHaveLength(2);
    expect(html).toContain('aria-label="文件面板宽度"'); expect(html).toContain('aria-label="预览面板宽度"');
    expect(html.match(/aria-disabled="true"/g)).toHaveLength(2);
  });
  it('通用上下分隔线提供数值与方向ARIA、键盘入口及独立恢复说明', () => {
    const html = renderToStaticMarkup(createElement(Separator, { orientation: 'horizontal', value: 320, min: 230, max: 500,
      label: '预览区域高度', onChange: vi.fn(), onReset: vi.fn() }));
    for (const attr of ['role="separator"', 'tabindex="0"', 'aria-orientation="horizontal"', 'aria-valuenow="320"',
      'aria-valuemin="230"', 'aria-valuemax="500"', 'aria-label="预览区域高度"']) expect(html).toContain(attr);
    expect(html).toContain('双击仅恢复此分隔线');
  });
});
