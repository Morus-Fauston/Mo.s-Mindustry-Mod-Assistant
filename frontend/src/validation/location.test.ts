import { expect, it } from 'vitest';
import type { FormField } from '../forms/types';
import type { NestedField, NestedFormPlan, ObjectPath } from '../nested/types';
import type { ValidationIssue } from './types';
import { resolveIssueField } from './location';

const damage: FormField = { name: 'damage', label: '伤害', help: '', javaType: 'float', mode: 'PRIMITIVE',
  control: 'number', fieldType: 'num', nullable: false, readOnly: false, deletable: true, present: true,
  value: 5, displayValue: 5, defaultValue: 0, defaultSource: '元数据', inactiveReason: '', validationError: '' };
const plan = (fields: NestedField[], objectPath: ObjectPath = []): NestedFormPlan => ({
  objectPath, contentType: 'Weapon', knownType: true, addableGroups: [],
  groups: [{ id: 'basic', label: '基础', locked: true, defaultExpanded: true, capability: false, enabled: true,
    fields, addableFields: [] }],
});
const issue = (extra: Partial<ValidationIssue> = {}): ValidationIssue => ({ id: 'issue', severity: 'error',
  message: '字段值无效', path: 'content/weapons/gun.json', field: 'damage', target: 'form', origin: 'content', ...extra });

it('只定位计划中明确存在的字段，不从消息或相似字段名推断', () => {
  const root = plan([damage]);
  expect(resolveIssueField(root, issue())).toEqual({ objectPath: [], field: 'damage' });
  expect(resolveIssueField(root, issue({ field: null }))).toBeNull();
  expect(resolveIssueField(root, issue({ field: 'damages' }))).toBeNull();
  expect(resolveIssueField(root, issue({ target: 'file' }))).toBeNull();
  expect(resolveIssueField(root, issue({ objectPath: ['bullet'] }))).toBeNull();
});

it('对象和数组数字下标逐级映射为当前计划的稳定 itemId', () => {
  const first = 'a'.repeat(32), second = 'b'.repeat(32);
  const nested = (itemId: string, index: number) => ({ itemId, index,
    form: plan([{ ...damage, name: 'bullet', control: 'object' as const, canCreate: false,
      child: plan([damage], ['weapons', { itemId }, 'bullet']) }], ['weapons', { itemId }]) });
  const root = plan([{ ...damage, name: 'weapons', control: 'array', canInsert: true, canMove: true, canRemove: true,
    items: [nested(first, 0), nested(second, 1)] }]);
  expect(resolveIssueField(root, issue({ objectPath: ['weapons', 1, 'bullet'] })))
    .toEqual({ objectPath: ['weapons', { itemId: second }, 'bullet'], field: 'damage' });
  const field = root.groups[0].fields[0];
  if (field.control !== 'array') throw new Error('测试数据应为数组');
  field.items = [nested(second, 0), nested(first, 1)];
  expect(resolveIssueField(root, issue({ objectPath: ['weapons', 1, 'bullet'] })))
    .toEqual({ objectPath: ['weapons', { itemId: first }, 'bullet'], field: 'damage' });
  for (const path of [['weapons', -1], ['weapons', 2], ['weapons', '1'], ['weapons', 0.5], ['weapons'], [0]]) {
    expect(resolveIssueField(root, issue({ objectPath: path }))).toBeNull();
  }
});

it('不可用能力组和失活父对象不打开；计划身份不一致时退回文件级', () => {
  const child = plan([damage], ['bullet']);
  const root = plan([{ ...damage, name: 'bullet', control: 'object', canCreate: false, child }]);
  const diagnostic = issue({ objectPath: ['bullet'] });
  root.groups[0].capability = true; root.groups[0].enabled = false;
  expect(resolveIssueField(root, diagnostic)).toBeNull();
  root.groups[0].enabled = true;
  root.groups[0].fields[0].inactiveReason = '此模式下不可用';
  expect(resolveIssueField(root, diagnostic)).toBeNull();
  root.groups[0].fields[0].inactiveReason = '';
  child.objectPath = ['different'];
  expect(resolveIssueField(root, diagnostic)).toBeNull();
  child.objectPath = ['bullet'];
  child.groups[0].capability = true; child.groups[0].enabled = false;
  expect(resolveIssueField(root, diagnostic)).toBeNull();
  child.groups[0].enabled = true;
  expect(resolveIssueField(root, diagnostic)).toEqual({ objectPath: ['bullet'], field: 'damage' });
});

it('武器内联表单与标量数组只按 DTO 身份定位，不支持的引用条目保持文件级', () => {
  const itemId = 'a'.repeat(32);
  const objectPath: ObjectPath = ['weapons', { itemId }];
  const root = plan([{ ...damage, name: 'weapons', control: 'weapon_array', objectPath: [],
    canInsert: true, canMove: true, canRemove: true, bulletTypes: [],
    items: [{ itemId, index: 0, objectPath, mode: 'inline', form: plan([damage], objectPath), canExpand: false, canCreateBlank: false }] }]);
  expect(resolveIssueField(root, issue({ objectPath: ['weapons', 0] }))).toEqual({ objectPath, field: 'damage' });
  const field = root.groups[0].fields[0];
  if (field.control !== 'weapon_array') throw new Error('测试数据应为武器数组');
  field.items[0].form = undefined;
  expect(resolveIssueField(root, issue({ objectPath: ['weapons', 0] }))).toBeNull();
  root.groups[0].fields = [{ ...damage, name: 'colors', control: 'array', canInsert: true, canMove: true, canRemove: true,
    items: [{ itemId, index: 0, field: { ...damage, name: 'value' } }] }];
  expect(resolveIssueField(root, issue({ objectPath: ['colors', 0], field: 'value' })))
    .toEqual({ objectPath: ['colors', { itemId }], field: 'value' });
  expect(resolveIssueField(root, issue({ objectPath: ['colors', 0], field: 'damage' }))).toBeNull();
});
