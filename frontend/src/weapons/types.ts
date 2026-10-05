import type { FormField } from '../forms/types';
import type { NestedFormPlan, ObjectPath } from '../nested/types';

export interface WeaponArrayItem {
  itemId: string;
  index: number;
  objectPath: ObjectPath;
  mode: 'reference' | 'inline' | 'unsupported';
  form?: NestedFormPlan;
  notice?: string;
  canExpand: boolean;
  canCreateBlank: boolean;
  overrideGroups?: { id: string; label: string; fields: { name: string; label: string; help: string; defaultValue: unknown }[] }[];
}
export interface WeaponArrayField extends Omit<FormField, 'control'> {
  control: 'weapon_array';
  objectPath: ObjectPath;
  items: WeaponArrayItem[];
  canInsert: boolean;
  canRemove: boolean;
  canMove: boolean;
  bulletTypes: { value: string; label: string }[];
}
export function isWeaponArrayField(value: unknown): value is WeaponArrayField {
  return value !== null && typeof value === 'object' && 'control' in value && value.control === 'weapon_array';
}
export interface WeaponCreationDraft { mode: 'reference' | 'inline'; reference: string | null; name: string; bulletType: string }

/** Creation buffers do not become document values until this request succeeds. */
export function weaponCreationPayload(field: WeaponArrayField, objectPath: ObjectPath, draft: WeaponCreationDraft): Record<string, unknown> {
  if (!field.canInsert || field.readOnly) throw new Error('此武器列表暂时不能添加条目。');
  const name = draft.mode === 'reference' ? draft.reference : draft.name.trim();
  if (!name) throw new Error(draft.mode === 'reference' ? '请先选择武器引用。' : '请输入武器名称。');
  if (draft.mode === 'inline' && !field.bulletTypes.some(choice => choice.value === draft.bulletType)) throw new Error('请选择支持的子弹类型。');
  return { objectPath, field: field.name, mode: draft.mode, name,
    ...(draft.mode === 'inline' ? { bulletType: draft.bulletType } : {}) };
}
