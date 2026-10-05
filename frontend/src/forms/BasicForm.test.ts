import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { BasicForm, type BasicFormProps } from './BasicForm';
import type { FormField } from './types';

const health: FormField = { name: 'health', label: '生命值', help: '单位生命值。', javaType: 'float', mode: 'PRIMITIVE',
  control: 'number', fieldType: 'num', nullable: false, readOnly: false, deletable: false,
  present: false, value: null, displayValue: 100, defaultValue: 100, defaultSource: '元数据', inactiveReason: '', validationError: '' };

function props(fields: FormField[]): BasicFormProps {
  return { document: { sessionId: 's', path: 'content/units/dagger.json', name: 'dagger', category: 'units', contentType: 'UnitType',
    data: {}, fieldNames: {}, fieldDocs: {}, revision: 1, dirty: false,
    form: { groups: [{ id: 'basic', label: '基础', locked: true, defaultExpanded: true, capability: false, enabled: true,
      fields, addableFields: [] }], addableGroups: [] } }, drafts: {}, errors: {}, disabled: false,
    onDraft: vi.fn(), onReset: vi.fn(), onComposition: vi.fn(), onCommit: vi.fn(async () => {}), onAction: vi.fn(async () => {}) };
}

describe('基础表单公开渲染', () => {
  it('初始化只显示后端缺省值，锁定组和保留字段无删除入口', () => {
    const input = props([health]);
    const html = renderToStaticMarkup(createElement(BasicForm, input));
    expect(html).toContain('value="100"');
    expect(html).toContain('未写入文件');
    expect(html).toContain('单位生命值。');
    expect(html).not.toContain('删除基础组');
    expect(html).not.toContain('生命值的操作');
    expect(input.onAction).not.toHaveBeenCalled();
    expect(input.onCommit).not.toHaveBeenCalled();
    expect(input.onDraft).not.toHaveBeenCalled();
  });

  it('非法草稿原样显示错误，依赖不生效独立于验证错误', () => {
    const inactive = { ...health, name: 'boostMultiplier', label: '助推倍率', inactiveReason: '需要开启助推。' };
    const input = props([health, inactive]);
    input.drafts = { health: '1e-' };
    input.errors = { health: '需要完整数字。' };
    const html = renderToStaticMarkup(createElement(BasicForm, input));
    expect(html).toContain('value="1e-"');
    expect(html).toContain('aria-label="生命值" aria-invalid="true"');
    expect(html).toContain('aria-label="助推倍率" aria-invalid="false"');
    expect(html).toContain('需要开启助推。');
    expect(html).toContain('需要完整数字。');
  });

  it('值只读的optional专用字段仍有后端许可的删除入口', () => {
    const input = props([{ ...health, name: 'shownPlanets', label: '可见星球', control: 'readonly',
      readOnly: true, deletable: true, nullable: true, present: true, value: [], displayValue: [] }]);
    const html = renderToStaticMarkup(createElement(BasicForm, input));
    expect(html).toContain('可见星球的操作');
    expect(html).not.toContain('删除基础组');
  });
});
