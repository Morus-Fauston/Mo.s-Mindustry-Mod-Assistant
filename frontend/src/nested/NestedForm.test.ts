import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { NestedForm, type NestedFormProps } from './NestedForm';
import { encodeFieldKey, findNestedField } from './address';
import type { FormField } from '../forms/types';
import type { NestedArrayField, NestedField, NestedFormPlan } from './types';

const itemId = 'a'.repeat(32);
const damage: FormField = { name: 'damage', label: '伤害', help: '子弹伤害。', javaType: 'float', mode: 'PRIMITIVE',
  control: 'number', fieldType: 'num', nullable: false, readOnly: false, deletable: false,
  present: true, value: 5, displayValue: 5, defaultValue: 0, defaultSource: '元数据', inactiveReason: '', validationError: '' };

function plan(fields: NestedField[], objectPath: NestedFormPlan['objectPath'] = []): NestedFormPlan {
  return { objectPath, contentType: 'Weapon', knownType: true,
    groups: [{ id: 'basic', label: '基础', locked: true, defaultExpanded: true, capability: false, enabled: true, fields, addableFields: [] }], addableGroups: [] };
}
function props(form: NestedFormPlan): NestedFormProps {
  return { document: { sessionId: 'session', path: 'content/weapons/gun.json', name: 'gun', category: 'weapons', contentType: 'Weapon',
    data: {}, fieldNames: { type: '类型' }, fieldDocs: {}, revision: 1, dirty: false, form: { groups: [], addableGroups: [] } },
    plan: form, drafts: {}, errors: {}, disabled: false, onDraft: vi.fn(), onCommit: vi.fn(async () => {}), onReset: vi.fn(),
    onComposition: vi.fn(), onAction: vi.fn(async () => {}),
    onLoadReference: vi.fn(async () => ({ candidates: [], categories: [], current: { value: null, label: '未选择', known: true } })) };
}
const bullet = (child: NestedFormPlan): NestedField => ({ ...damage, name: 'bullet', label: '子弹', control: 'object', fieldType: 'obj', mode: 'INLINE_OBJECT', child, canCreate: false });

describe('嵌套表单公开渲染', () => {
  it('已知基础类型不在子类候选中时仍正确识别', () => {
    const child = plan([damage], ['bullet']);
    child.typeSelector = { value: 'BulletType', choices: [{ value: 'BasicBulletType', label: '基础子弹' }] };
    const html = renderToStaticMarkup(createElement(NestedForm, props(plan([bullet(child)]))));
    expect(html).toContain('当前基础类型：BulletType');
    expect(html).not.toContain('未识别类型');
  });

  it('复用基础字段与引用控件，草稿和错误按完整地址隔离', () => {
    const child = plan([damage, { ...damage, name: 'status', label: '状态', control: 'reference', fieldType: 'ref', value: 'burning', displayValue: 'burning' }], ['bullet']);
    const input = props(plan([damage, bullet(child)]));
    input.drafts = { [encodeFieldKey(['bullet'], 'damage')]: '1e-' };
    input.errors = { [encodeFieldKey(['bullet'], 'damage')]: '请输入完整数字。' };
    const html = renderToStaticMarkup(createElement(NestedForm, input));
    expect(html).toContain('value="5"');
    expect(html).toContain('value="1e-"');
    expect(html).toContain('请输入完整数字。');
    expect(html).toContain('aria-label="状态"');
    expect(html).toContain('data-field-type="obj"');
    expect(input.onAction).not.toHaveBeenCalled();
    expect(input.onDraft).not.toHaveBeenCalled();
    expect(input.onCommit).not.toHaveBeenCalled();
  });

  it('未知类型原样显示，不默认提交第一个候选', () => {
    const child = plan([damage], ['bullet']);
    child.knownType = false;
    child.notice = '未识别此类型，原值已保留。';
    child.typeSelector = { value: 'CustomBullet', choices: [{ value: 'BasicBulletType', label: '基础子弹' }] };
    const input = props(plan([bullet(child)]));
    const html = renderToStaticMarkup(createElement(NestedForm, input));
    expect(html).toContain('value="CustomBullet"');
    expect(html).toContain('未识别类型：CustomBullet');
    expect(html).toContain('未识别此类型，原值已保留。');
    expect(input.onAction).not.toHaveBeenCalled();
  });

  it('数组展示后端身份与动作，标量地址可供统一草稿store查找', () => {
    const scalar: FormField = { ...damage, name: 'value', label: '值', control: 'color', fieldType: 'col', value: 'ff0000', displayValue: 'ff0000' };
    const array: NestedArrayField = { ...damage, name: 'colors', label: '颜色', control: 'array', fieldType: 'arr', mode: 'ARRAY',
      items: [{ itemId, index: 0, field: scalar }], canInsert: true, canRemove: true, canMove: false };
    const child = plan([array], ['bullet']);
    const input = props(plan([bullet(child)]));
    const key = encodeFieldKey(['bullet', 'colors', { itemId }], 'value');
    input.drafts = { [key]: '坏颜色草稿' };
    const html = renderToStaticMarkup(createElement(NestedForm, input));
    expect(html).toContain(`data-item-id="${itemId}"`);
    expect(html).toContain('坏颜色草稿');
    expect(html).toContain('添加颜色项');
    expect(html).toContain('删除第 1 项');
    expect(findNestedField(input.plan, key)).toBe(scalar);
    expect(findNestedField(input.plan, encodeFieldKey(['bullet', 'colors', { itemId: 'b'.repeat(32) }], 'value'))).toBeUndefined();
  });

  it('缺失对象只提供明确创建入口，非法原值保持只读', () => {
    const input = props(plan([{ ...damage, name: 'bullet', label: '子弹', control: 'object', fieldType: 'obj', child: undefined, canCreate: true }]));
    const html = renderToStaticMarkup(createElement(NestedForm, input));
    expect(html).toContain('创建子弹');
    expect(input.onAction).not.toHaveBeenCalled();
    input.plan.groups[0].fields = [{ ...damage, name: 'bullet', label: '子弹', control: 'object', fieldType: 'obj', child: undefined,
      canCreate: false, readOnly: true, displayValue: '原有引用', validationError: '对象格式无效。' }];
    const invalid = renderToStaticMarkup(createElement(NestedForm, input));
    expect(invalid).toContain('原有引用');
    expect(invalid).toContain('对象格式无效。');
    expect(invalid).not.toContain('创建子弹');
  });
});
