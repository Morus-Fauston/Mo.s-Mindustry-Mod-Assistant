import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { LayerTree, type LayerTreeProps } from './LayerTree';
import { encodeFieldKey } from '../nested/address';
import type { FormField } from '../forms/types';
import type { LayerNode } from './types';

const itemId = 'a'.repeat(32), objectPath = ['weapons', { itemId }];
const coordinate = (name: string): FormField => ({ name, label: name, help: '', javaType: 'float', mode: 'PRIMITIVE',
  control: 'number', fieldType: 'num', nullable: false, readOnly: false, deletable: true, present: true,
  value: -3, displayValue: -3, defaultValue: 0, defaultSource: '', inactiveReason: '', validationError: '' });
function props(): LayerTreeProps {
  const nodes: LayerNode[] = [
    { id: 'sprite:', kind: 'sprite', label: '主体', status: 'missing', drawableKeys: [''] },
    { id: 'group:weapons', kind: 'weapon-group', label: '武器', children: [
      { id: `weapon:${itemId}`, kind: 'weapon', label: '双联炮', status: 'ready', drawableKeys: ['__weapon_0__'],
        weapon: { itemId, objectPath, coordinates: { x: coordinate('x'), y: coordinate('y') } } },
    ] },
  ];
  return { sessionId: 'session', path: 'content/units/unit.json', nodes, selectedId: `weapon:${itemId}`,
    hiddenIds: [`weapon:${itemId}`], closedIds: [], disabled: false, drafts: {}, errors: {},
    fieldNames: { x: 'X偏移', y: 'Y偏移' }, fieldDocs: { x: '横向安装坐标', y: '纵向安装坐标' },
    onSelect: vi.fn(), onVisibility: vi.fn(), onExpanded: vi.fn(), onRevealParameters: vi.fn(),
    onDraft: vi.fn(), onCommit: vi.fn(async () => {}), onReset: vi.fn(), onComposition: vi.fn() };
}

describe('真实图层 DTO 的受控树视图', () => {
  it('稳定身份、独立热区及共享草稿错误渲染，挂载不执行任何业务或视图动作', () => {
    const input = props();
    input.drafts[encodeFieldKey(objectPath, 'x')] = '-4.25';
    input.errors[encodeFieldKey(objectPath, 'y')] = '请输入有限数字。';
    const html = renderToStaticMarkup(createElement(LayerTree, input));
    expect(html).toContain('role="tree"');
    expect(html).toContain(`data-layer-id="weapon:${itemId}"`);
    expect(html).toContain('aria-label="选择双联炮图层"');
    expect(html).toContain('aria-label="显示双联炮图层"');
    expect(html).toContain('aria-label="折叠武器"');
    expect(html).toContain('aria-label="定位双联炮参数"');
    expect(html).toContain('value="-4.25"');
    expect(html).toContain('X偏移'); expect(html).toContain('横向安装坐标');
    expect(html).toContain('请输入有限数字。'); expect(html).toContain('aria-invalid="true"');
    expect(html).not.toContain('删除字段');
    expect(input.onSelect).not.toHaveBeenCalled(); expect(input.onVisibility).not.toHaveBeenCalled();
    expect(input.onExpanded).not.toHaveBeenCalled(); expect(input.onDraft).not.toHaveBeenCalled();
    expect(input.onCommit).not.toHaveBeenCalled();
  });

  it('折叠只隐藏武器行，缺图或只读坐标仍可理解且没有新增写入口', () => {
    const input = props();
    input.closedIds = ['group:weapons'];
    let html = renderToStaticMarkup(createElement(LayerTree, input));
    expect(html).toContain('aria-label="展开武器"');
    expect(html).not.toContain('aria-label="定位双联炮参数"');
    expect(html).toContain('缺失');
    input.closedIds = [];
    const weapon = input.nodes[1].children![0];
    weapon.weapon!.coordinates.x!.readOnly = true;
    weapon.notice = '未找到贴图，仍可编辑安装坐标。';
    input.disabled = true;
    html = renderToStaticMarkup(createElement(LayerTree, input));
    expect(html).toMatch(/<output[^>]*aria-label="X偏移"[^>]*>-3<\/output>/);
    expect(html).toMatch(/<input[^>]*aria-label="Y偏移"[^>]*disabled=""/);
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*aria-label="定位双联炮参数"/);
    expect(html).toContain('未找到贴图，仍可编辑安装坐标。');
    expect(input.onCommit).not.toHaveBeenCalled();
  });
});
