import type { FormDrafts, FormErrors } from '../forms/types';
import type { NestedField, NestedFormPlan, ObjectPath } from './types';

const prefix = '@nested:';
const fieldName = /^[A-Za-z_][A-Za-z_0-9]*$/;
const itemId = /^[0-9a-f]{32}$/;

function validPath(value: unknown): value is ObjectPath {
  return Array.isArray(value) && value.length <= 12 && value.every(segment =>
    typeof segment === 'string' ? fieldName.test(segment)
      : segment !== null && typeof segment === 'object' && Object.keys(segment).length === 1
        && typeof segment.itemId === 'string' && itemId.test(segment.itemId));
}

/** Keys address input buffers only; they never enter the saved document. */
export function encodeFieldKey(objectPath: ObjectPath, field: string): string {
  if (!validPath(objectPath) || !fieldName.test(field)) throw new Error('字段地址无效。');
  return objectPath.length ? `${prefix}${JSON.stringify([objectPath, field])}` : field;
}

export function decodeFieldKey(key: string): { objectPath: ObjectPath; field: string } {
  if (!key.startsWith(prefix)) {
    if (!fieldName.test(key)) throw new Error('字段地址无效。');
    return { objectPath: [], field: key };
  }
  let parsed: unknown;
  try { parsed = JSON.parse(key.slice(prefix.length)); } catch { throw new Error('字段地址无效。'); }
  if (!Array.isArray(parsed) || parsed.length !== 2 || !validPath(parsed[0]) || typeof parsed[1] !== 'string' || !fieldName.test(parsed[1])) {
    throw new Error('字段地址无效。');
  }
  return { objectPath: parsed[0], field: parsed[1] };
}

export function scopedFields(records: FormDrafts | FormErrors, objectPath: ObjectPath, fields: NestedField[]): Record<string, string> {
  const result: Record<string, string> = {};
  for (const field of fields) {
    const key = encodeFieldKey(objectPath, field.name);
    if (Object.hasOwn(records, key)) result[field.name] = records[key];
  }
  return result;
}

/** Public plan lookup for the root draft store's current-value/no-op checks. */
export function findNestedField(plan: NestedFormPlan, key: string): NestedField | undefined {
  const address = decodeFieldKey(key);
  const target = JSON.stringify(address.objectPath);
  const visit = (node: NestedFormPlan): NestedField | undefined => {
    if (JSON.stringify(node.objectPath) === target) return node.groups.flatMap(group => group.fields).find(field => field.name === address.field);
    for (const field of node.groups.flatMap(group => group.fields)) {
      if (field.control === 'object' && field.child) {
        const found = visit(field.child); if (found) return found;
      }
      if (field.control === 'array') for (const item of field.items) {
        if (item.form) { const found = visit(item.form); if (found) return found; }
        if (item.field && JSON.stringify([...node.objectPath, field.name, { itemId: item.itemId }]) === target && address.field === 'value') return item.field;
      }
    }
    return undefined;
  };
  return visit(plan);
}

export function moveBefore(items: { itemId: string }[], id: string, direction: 'up' | 'down'): string | null | undefined {
  const index = items.findIndex(item => item.itemId === id);
  if (index < 0 || direction === 'up' && index === 0 || direction === 'down' && index === items.length - 1) return undefined;
  return direction === 'up' ? items[index - 1].itemId : items[index + 2]?.itemId ?? null;
}
