import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { FormField } from '../forms/types';
import { encodeFieldKey } from '../nested/address';
import type { NestedField, NestedFormPlan } from '../nested/types';
import { ResourceField, type ResourceFieldProps } from './ResourceField';
import { findResourceField, resourceLeafProps } from './address';
import type { ConsumesField, ResourceDescriptor, ResourceListField, ResourceSlotField } from './types';

const itemId = 'a'.repeat(32);
const amount: FormField = { name: 'amount', label: '数量', help: '资源数量。', javaType: 'int', mode: 'PRIMITIVE',
  control: 'number', fieldType: 'num', integer: true, nullable: false, readOnly: false, deletable: false,
  present: true, value: 2, displayValue: 2, defaultValue: 1, defaultSource: '既有资源默认值', inactiveReason: '', validationError: '' };
const item: FormField = { ...amount, name: 'item', label: '物品', javaType: 'String', control: 'reference',
  fieldType: 'ref', mode: 'STRING_REF', value: '', displayValue: '', categories: ['Items'] };
const requirements = (): ResourceListField => ({ ...amount, name: 'requirements', label: '建造需求', control: 'resource_list', fieldType: 'arr',
  objectPath: ['requirements'], resourceType: 'item', canInsert: true, canRemove: true, canMove: false,
  rows: [{ itemId, objectPath: ['requirements', { itemId }], fields: [item, amount] }] });
const slot = (): ResourceSlotField => ({ ...amount, name: 'outputItem', label: '输出物品', control: 'resource_slot', fieldType: 'ref',
  objectPath: ['outputItem'], empty: true, fields: [{ ...item, nullable: true, value: null, displayValue: '' }, { ...amount, readOnly: true }] });
const power: FormField = { ...amount, name: 'power', label: '电力', integer: false, value: 0, displayValue: 0 };
const consumes = (): ConsumesField => ({ ...amount, name: 'consumes', label: '消耗', control: 'consumes', fieldType: 'obj',
  objectPath: ['consumes'], children: [power], addable: [{ name: 'liquid', label: '液体' }] });

function props(field: ResourceDescriptor): ResourceFieldProps {
  return { field, objectPath: [], document: { sessionId: 'session', path: 'content/blocks/crafter.json', name: 'crafter', category: 'blocks',
    contentType: 'GenericCrafter', data: {}, fieldNames: {}, fieldDocs: {}, revision: 1, dirty: false, form: { groups: [], addableGroups: [] } },
    drafts: {}, errors: {}, disabled: false, onDraft: vi.fn(), onCommit: vi.fn(async () => {}), onReset: vi.fn(),
    onComposition: vi.fn(), onAction: vi.fn(async () => {}),
    onLoadReference: vi.fn(async () => ({ candidates: [], categories: [], current: { value: null, label: '未选择', known: true } })) };
}
function plan(field: ResourceDescriptor): NestedFormPlan {
  return { objectPath: [], contentType: 'GenericCrafter', knownType: true,
    groups: [{ id: 'basic', label: '基础', locked: true, defaultExpanded: true, capability: false, enabled: true,
      fields: [field as unknown as NestedField], addableFields: [] }], addableGroups: [] };
}

describe('资源专用编辑器', () => {
  it('列表复用真实引用和基础数字输入，使用稳定条目标识且重建不提交', () => {
    const field = requirements();
    const input = props(field);
    const key = encodeFieldKey(field.rows[0].objectPath, 'amount');
    input.drafts = { [key]: '1e-' };
    input.errors = { [key]: '请输入完整数量。' };
    const html = renderToStaticMarkup(createElement(ResourceField, input));
    expect(html).toContain(`data-item-id="${itemId}"`);
    expect(html).toContain('value="1e-"');
    expect(html).toContain('请输入完整数量。');
    expect(html).toContain('aria-label="物品"');
    expect(html).toContain('data-field-type="arr"');
    expect(html).toContain('添加建造需求项');
    expect(html).toContain('删除第 1 项');
    expect(input.onAction).not.toHaveBeenCalled();
    expect(input.onDraft).not.toHaveBeenCalled();
    expect(input.onCommit).not.toHaveBeenCalled();
  });

  it('空槽保留可选择的引用与只读数量，零电力按零显示', () => {
    const empty = props(slot());
    const html = renderToStaticMarkup(createElement(ResourceField, empty));
    expect(html).toContain('aria-label="物品"');
    expect(html).toContain('<output');
    expect(empty.onAction).not.toHaveBeenCalled();
    const consume = props(consumes());
    const zero = renderToStaticMarkup(createElement(ResourceField, consume));
    expect(zero).toContain('value="0"');
    expect(zero).toContain('移除电力消耗');
    expect(zero).toContain('添加消耗子项');
    expect(consume.onAction).not.toHaveBeenCalled();
  });

  it('非法资源原值和行保持可见，无数量输入或默认重写', () => {
    const invalid = props({ ...slot(), readOnly: true, displayValue: 'copper/2', validationError: '资源槽格式无效，原值已保留。' });
    const html = renderToStaticMarkup(createElement(ResourceField, invalid));
    expect(html).toContain('copper/2');
    expect(html).toContain('资源槽格式无效');
    expect(html).not.toContain('aria-label="数量"');
    const list = requirements();
    list.rows[0] = { ...list.rows[0], fields: [], notice: '此资源项不是已有字典格式，原值已保留。' };
    expect(renderToStaticMarkup(createElement(ResourceField, props(list)))).toContain('此资源项不是已有字典格式');
    expect(invalid.onAction).not.toHaveBeenCalled();
  });

  it('基础回调全部使用同一完整地址，空值与零直接交给后端', async () => {
    const field = requirements();
    const input = props(field);
    const path = field.rows[0].objectPath;
    const leaf = resourceLeafProps(input, path, field.rows[0].fields);
    const key = encodeFieldKey(path, 'amount');
    leaf.onDraft('amount', ''); await leaf.onCommit('amount'); leaf.onReset('amount'); leaf.onComposition('amount', true);
    await leaf.onLoadReference('item', '铜');
    expect(input.onDraft).toHaveBeenCalledWith(key, '');
    expect(input.onCommit).toHaveBeenCalledWith(key);
    expect(input.onReset).toHaveBeenCalledWith(key);
    expect(input.onComposition).toHaveBeenCalledWith(key, true);
    expect(input.onLoadReference).toHaveBeenCalledWith(encodeFieldKey(path, 'item'), '铜');
    await leaf.onAction('set_field', { field: 'item', value: '' });
    expect(input.onAction).toHaveBeenLastCalledWith('resource_set', { objectPath: path, field: 'item', value: '' });
    await resourceLeafProps(input, ['outputItem'], slot().fields).onAction('set_field', { field: 'item', value: null });
    expect(input.onAction).toHaveBeenLastCalledWith('resource_set', { objectPath: ['outputItem'], field: 'item', value: null });
    await resourceLeafProps(input, ['consumes'], [power]).onAction('set_field', { field: 'power', value: 0 });
    expect(input.onAction).toHaveBeenLastCalledWith('resource_set', { objectPath: ['consumes'], field: 'power', value: 0 });
    await expect(leaf.onAction('delete_field', { field: 'amount' })).rejects.toThrow('不支持');
  });

  it('统一草稿查询定位列表、槽位与消耗叶子，删除后的旧标识不命中', () => {
    const list = requirements();
    expect(findResourceField(plan(list), encodeFieldKey(list.rows[0].objectPath, 'amount'))).toBe(amount);
    expect(findResourceField(plan(list), encodeFieldKey(['requirements', { itemId: 'b'.repeat(32) }], 'amount'))).toBeUndefined();
    const output = slot();
    expect(findResourceField(plan(output), encodeFieldKey(['outputItem'], 'item'))).toBe(output.fields[0]);
    const consume = consumes();
    const liquids = { ...list, name: 'liquids', objectPath: ['consumes', 'liquids'], rows: [
      { itemId, objectPath: ['consumes', 'liquids', { itemId }], fields: [amount] },
    ] } satisfies ResourceListField;
    consume.children.push(liquids);
    expect(findResourceField(plan(consume), encodeFieldKey(['consumes'], 'power'))).toBe(power);
    expect(findResourceField(plan(consume), encodeFieldKey(liquids.rows[0].objectPath, 'amount'))).toBe(amount);
  });
});
