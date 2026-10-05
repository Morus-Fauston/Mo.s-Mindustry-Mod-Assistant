import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { ComparisonTable, ReferenceComparison, type ReferenceComparisonProps } from './ReferenceComparison';
import type { Comparison } from './types';
import * as controllers from './controller';

describe('只读参考界面', () => {
  it('前端草稿只禁比较和刷新，仍可打开参考来源', async () => {
    const comparison: Comparison = { sessionId: 's', sourceId: 'vanilla', category: 'units', name: 'dagger',
      currentPath: 'content/units/a.json', revision: 2, rows: [] };
    const props: ReferenceComparisonProps = { sessionId: 's', path: comparison.currentPath, revision: 2,
      fieldNames: {}, fieldDocs: {}, disabled: false, compareDisabled: true,
      onOpen: vi.fn(), onSources: vi.fn(async () => ({ sources: [] })), onCandidates: vi.fn(),
      onCompare: vi.fn(async () => comparison), onRelease: vi.fn() };
    const controller = controllers.createComparisonController();
    controller.start('s', comparison.currentPath, 2, props);
    await controller.compare('vanilla', 'units', 'dagger');
    const factory = vi.spyOn(controllers, 'createComparisonController').mockReturnValue(controller);
    try {
      const html = renderToStaticMarkup(createElement(ReferenceComparison, props));
      const refresh = html.match(/<button[^>]*>刷新当前对比<\/button>/)?.[0];
      expect(refresh).toContain('disabled');
      expect(html.match(/<button[^>]*>打开参考目录<\/button>/)?.[0]).not.toContain('disabled');
      expect(html.match(/<button[^>]*>打开参考压缩包<\/button>/)?.[0]).not.toContain('disabled');
      const enabled = renderToStaticMarkup(createElement(ReferenceComparison, { ...props, compareDisabled: false }));
      expect(enabled.match(/<button[^>]*>刷新当前对比<\/button>/)?.[0]).not.toContain('disabled');
    } finally { factory.mockRestore(); controller.stop(); }
  });

  it('只提供参考读取和比较入口，空文档有中文反馈，渲染不导入或写入', () => {
    const props: ReferenceComparisonProps = { sessionId: '甲', path: '', revision: 0, fieldNames: {}, fieldDocs: {}, disabled: false,
      onOpen: vi.fn(), onSources: vi.fn(), onCandidates: vi.fn(), onCompare: vi.fn(), onRelease: vi.fn() };
    const html = renderToStaticMarkup(createElement(ReferenceComparison, props));
    expect(html).toContain('打开参考目录'); expect(html).toContain('打开参考压缩包');
    expect(html).toContain('中文名称或英文标识'); expect(html).toContain('请先打开一个内容文件');
    expect(html).not.toContain('应用参考'); expect(html).not.toContain('保存');
    expect(props.onOpen).not.toHaveBeenCalled(); expect(props.onCompare).not.toHaveBeenCalled();
    expect(props.onRelease).not.toHaveBeenCalled();
  });

  it('字段名与提示来自配置，缺失空值类型明确，未知字段保留并安全显示', () => {
    const comparison: Comparison = { sessionId: '甲', sourceId: 'vanilla', category: 'Units', name: '参考',
      currentPath: 'content/units/当前.json', revision: 2, rows: [
        { field: 'health', current: { present: false, kind: 'missing', text: '未设置', truncated: false },
          reference: { present: true, kind: 'null', text: 'null', truncated: false }, different: true },
        { field: '<unknown>', current: { present: true, kind: 'string', text: '<script>bad()</script>', truncated: true },
          reference: { present: true, kind: 'nonfinite', text: 'Infinity', truncated: false }, different: true },
      ] };
    const html = renderToStaticMarkup(createElement(ComparisonTable, { comparison,
      fieldNames: { health: '配置中的生命值' }, fieldDocs: { health: '配置中的说明' } }));
    expect(html).toContain('配置中的生命值'); expect(html).toContain('title="配置中的说明"');
    expect(html).toContain('未设置'); expect(html).toContain('空值'); expect(html).toContain('非有限数字');
    expect(html).toContain('显示已截断'); expect(html).toContain('&lt;unknown&gt;');
    expect(html).toContain('&lt;script&gt;'); expect(html).not.toContain('<script>');
    expect(html).toContain('2 项不同'); expect(html).toContain('data-different="true"');
    expect(html).not.toContain('<input'); expect(html).not.toContain('contenteditable');
    expect(html).toContain('scope="row"'); expect(html).toContain('content/units/当前.json');
  });
});
