import { decodeFieldKey } from '../nested/address';
import type { NestedField, NestedFormPlan } from '../nested/types';
import { findResourceField } from '../resource_fields/address';
import { isWeaponArrayField, type WeaponArrayField } from './types';

/** Follows server item forms, including recursively spawned units and bullets. */
export function findWeaponField(plan: NestedFormPlan, key: string): NestedField | WeaponArrayField | undefined {
  const { objectPath, field: name } = decodeFieldKey(key);
  const target = JSON.stringify(objectPath);
  const visit = (node: NestedFormPlan, insideWeapon: boolean): NestedField | WeaponArrayField | undefined => {
    const fields = node.groups.flatMap(group => group.fields) as (NestedField | WeaponArrayField)[];
    if (insideWeapon && JSON.stringify(node.objectPath) === target) return fields.find(field => field.name === name);
    if (insideWeapon) { const found = findResourceField(node, key); if (found) return found; }
    for (const field of fields) {
      if (isWeaponArrayField(field)) {
        if (JSON.stringify(node.objectPath) === target && field.name === name) return field;
        for (const item of field.items) if (item.form) {
          const found = visit(item.form, true); if (found) return found;
        }
      } else if (field.control === 'object' && field.child) {
        const found = visit(field.child, insideWeapon); if (found) return found;
      } else if (field.control === 'array') for (const item of field.items) {
        if (item.form) { const found = visit(item.form, insideWeapon); if (found) return found; }
        if (insideWeapon && item.field && name === 'value'
          && JSON.stringify([...node.objectPath, field.name, { itemId: item.itemId }]) === target) return item.field;
      }
    }
    return undefined;
  };
  return visit(plan, false);
}
