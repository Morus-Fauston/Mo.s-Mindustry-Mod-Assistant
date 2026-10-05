import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import type { FormField } from '../forms/types';
import type { NestedField, NestedFormPlan, ObjectPath } from '../nested/types';
import { encodeFieldKey } from '../nested/address';
import { WeaponArray, type WeaponArrayProps } from './WeaponArray';
import { findWeaponField } from './address';
import { weaponCreationPayload, type WeaponArrayField } from './types';

const first = 'a'.repeat(32), second = 'b'.repeat(32), scalarId = 'c'.repeat(32);
const damage: FormField = { name: 'damage', label: '伤害', help: '子弹伤害。', javaType: 'float', mode: 'PRIMITIVE',
  control: 'number', fieldType: 'num', nullable: false, readOnly: false, deletable: false,
  present: true, value: 5, displayValue: 5, defaultValue: 0, defaultSource: '元数据', inactiveReason: '', validationError: '' };
function plan(fields: (NestedField | WeaponArrayField)[], objectPath: ObjectPath = []): NestedFormPlan {
  return { objectPath, contentType: 'Weapon', knownType: true, groups: [{ id: 'basic', label: '基础', locked: true,
    defaultExpanded: true, capability: false, enabled: true, fields: fields as NestedField[], addableFields: [] }], addableGroups: [] };
}
function weapon(): WeaponArrayField {
  return { ...damage, name: 'weapons', label: '武器列表', control: 'weapon_array', fieldType: 'arr', objectPath: ['weapons'],
    canInsert: true, canRemove: true, canMove: true,
    bulletTypes: [{ value: 'BasicBulletType', label: '基础子弹' }, { value: 'LaserBulletType', label: '激光子弹' }],
    items: [
      { itemId: first, index: 0, objectPath: ['weapons', { itemId: first }], mode: 'reference', canExpand: false, canCreateBlank: true,
        form: plan([{ ...damage, name: 'name', label: '名称', control: 'reference', fieldType: 'ref', displayValue: 'same' }], ['weapons', { itemId: first }]),
        overrideGroups: [{ id: 'behavior', label: '行为', fields: [{ name: 'rotate', label: '旋转', help: '', defaultValue: false }] }] },
      { itemId: second, index: 1, objectPath: ['weapons', { itemId: second }], mode: 'inline', canExpand: false, canCreateBlank: false,
        form: plan([damage], ['weapons', { itemId: second }]) },
    ] };
}
function props(field = weapon()): WeaponArrayProps {
  return { field, objectPath: [], document: { sessionId: 'session', path: 'content/units/unit.json', name: 'unit', category: 'units',
    contentType: 'UnitType', data: {}, fieldNames: { name: '名称', bullet: '子弹', type: '类型' }, fieldDocs: {}, revision: 1, dirty: false,
    form: { groups: [], addableGroups: [] } }, drafts: {}, errors: {}, disabled: false, onDraft: vi.fn(), onCommit: vi.fn(async () => {}),
    onReset: vi.fn(), onComposition: vi.fn(), onAction: vi.fn(async () => {}),
    onLoadReference: vi.fn(async () => ({ candidates: [], categories: [], current: { value: null, label: '未选择', known: true } })),
    renderForm: vi.fn(child => createElement('div', { 'data-render-path': JSON.stringify(child.objectPath) }, '实际子表单插槽')) };
}

describe('武器专用列表与创建缓冲', () => {
  it('以稳定条目标识渲染并交给现有子表单，不在挂载时产生业务动作', () => {
    const input = props();
    const html = renderToStaticMarkup(createElement(WeaponArray, input));
    expect(html).toContain(`data-item-id="${first}"`); expect(html).toContain(`data-item-id="${second}"`);
    expect(html).toContain('data-weapon-mode="reference"'); expect(html).toContain('data-weapon-mode="inline"');
    expect(html).toContain('实际子表单插槽'); expect(html).toContain('添加行为覆盖字段');
    expect(input.renderForm).toHaveBeenCalledWith(input.field.items[0].form);
    expect(input.onAction).not.toHaveBeenCalled(); expect(input.onDraft).not.toHaveBeenCalled(); expect(input.onCommit).not.toHaveBeenCalled();
  });

  it('缺源只提供显式空白入口，不自动展开或预先确认；非法原值保留可见', () => {
    const input = props();
    const html = renderToStaticMarkup(createElement(WeaponArray, input));
    expect(html).toContain('创建空白内联'); expect(html).not.toContain('确认创建空白内联'); expect(html).not.toContain('展开为内联');
    input.field.items[0].canExpand = true; input.field.items[0].canCreateBlank = false;
    expect(renderToStaticMarkup(createElement(WeaponArray, input))).toContain('展开为内联');
    input.field = { ...input.field, readOnly: true, displayValue: 'legacy-weapons', validationError: '武器数组格式无效。' };
    const readonly = renderToStaticMarkup(createElement(WeaponArray, input));
    expect(readonly).toContain('legacy-weapons'); expect(readonly).toContain('武器数组格式无效'); expect(readonly).not.toContain('添加武器');
    expect(input.onAction).not.toHaveBeenCalled();
  });

  it('创建请求保留真实引用值或显式内联名字与子弹类型，不生成本地业务对象', () => {
    const field = weapon();
    expect(weaponCreationPayload(field, [], { mode: 'reference', reference: 'probe-gun', name: '未使用名称', bulletType: '' })).toEqual({
      objectPath: [], field: 'weapons', mode: 'reference', name: 'probe-gun',
    });
    expect(weaponCreationPayload(field, ['spawnUnit'], { mode: 'inline', reference: 'ignored', name: '  same  ', bulletType: 'LaserBulletType' })).toEqual({
      objectPath: ['spawnUnit'], field: 'weapons', mode: 'inline', name: 'same', bulletType: 'LaserBulletType',
    });
    expect(() => weaponCreationPayload(field, [], { mode: 'reference', reference: null, name: '', bulletType: '' })).toThrow('请先选择');
    expect(() => weaponCreationPayload(field, [], { mode: 'inline', reference: null, name: '', bulletType: 'BasicBulletType' })).toThrow('请输入');
    expect(() => weaponCreationPayload(field, [], { mode: 'inline', reference: null, name: 'same', bulletType: 'Unknown' })).toThrow('请选择支持');
  });

  it('草稿查询覆盖引用、内嵌子弹和标量数组，不使用名字或行号定位', () => {
    const field = weapon();
    const bulletPath: ObjectPath = [...field.items[1].objectPath, 'bullet'];
    const scalar = { ...damage, name: 'value', label: '值', control: 'color' as const };
    field.items[1].form = plan([{ ...damage, name: 'bullet', label: '子弹', control: 'object', canCreate: false,
      child: plan([damage, { ...damage, name: 'colors', control: 'array', canInsert: true, canRemove: true, canMove: false,
        items: [{ itemId: scalarId, index: 0, field: scalar }] }], bulletPath) }], field.items[1].objectPath);
    const root = plan([field]);
    expect(findWeaponField(root, 'weapons')).toBe(field);
    expect(findWeaponField(root, encodeFieldKey(field.items[0].objectPath, 'name'))?.control).toBe('reference');
    expect(findWeaponField(root, encodeFieldKey(bulletPath, 'damage'))).toBe(damage);
    expect(findWeaponField(root, encodeFieldKey([...bulletPath, 'colors', { itemId: scalarId }], 'value'))).toBe(scalar);
    expect(findWeaponField(root, encodeFieldKey(['weapons', { itemId: 'd'.repeat(32) }], 'name'))).toBeUndefined();
    expect(findWeaponField(plan([damage]), 'damage')).toBeUndefined();
  });
});
