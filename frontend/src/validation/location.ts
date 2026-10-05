import type { NestedField, NestedFormPlan, ObjectPath } from '../nested/types';
import type { ValidationIssue } from './types';

const namePattern = /^[A-Za-z_][A-Za-z_0-9]*$/;

function availableField(plan: NestedFormPlan, name: string): NestedField | null {
  const matches = plan.groups.flatMap(group => group.fields.filter(field => field.name === name)
    .map(field => ({ group, field })));
  if (matches.length !== 1) return null;
  const { group, field } = matches[0];
  return group.capability && !group.enabled || field.inactiveReason ? null : field;
}

/** Caller must first match the report's session and revision to this current plan. */
export function resolveIssueField(plan: NestedFormPlan, issue: ValidationIssue): { objectPath: ObjectPath; field: string } | null {
  if (issue.target !== 'form' || !issue.field || !namePattern.test(issue.field)
      || plan.objectPath.length || issue.objectPath !== undefined && !Array.isArray(issue.objectPath)) return null;
  const path = issue.objectPath ?? [];
  if (path.length > 12) return null;
  let current = plan;
  let objectPath: ObjectPath = [];
  for (let position = 0; position < path.length; position++) {
    const name = path[position];
    if (typeof name !== 'string' || !namePattern.test(name)) return null;
    const field = availableField(current, name);
    if (!field || field.readOnly) return null;
    if (field.control === 'object' && field.child) {
      objectPath = [...objectPath, name];
      current = field.child;
    } else if (field.control === 'array' || field.control === 'weapon_array') {
      const index = path[++position];
      if (typeof index !== 'number' || !Number.isSafeInteger(index) || index < 0) return null;
      const matches = field.items.filter(item => item.index === index);
      if (matches.length !== 1) return null;
      const item = matches[0];
      if (!/^[0-9a-f]{32}$/.test(item.itemId) || field.items.filter(other => other.itemId === item.itemId).length !== 1) return null;
      objectPath = [...objectPath, name, { itemId: item.itemId }];
      if (item.form) current = item.form;
      else if ('field' in item && item.field && position === path.length - 1 && item.field.name === issue.field
          && !item.field.inactiveReason) return { objectPath, field: issue.field };
      else return null;
    } else return null;
    if (JSON.stringify(current.objectPath) !== JSON.stringify(objectPath)) return null;
  }
  return availableField(current, issue.field) ? { objectPath, field: issue.field } : null;
}
