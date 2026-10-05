import type { BasicFormProps } from '../forms/BasicForm';
import type { FormField } from '../forms/types';
import { decodeFieldKey, encodeFieldKey, scopedFields } from '../nested/address';
import type { NestedFormPlan, ObjectPath } from '../nested/types';
import { isResourceField, type ResourceDescriptor } from './types';

/** Shared buffers and basic controls keep one canonical address namespace. */
export function resourceLeafProps(root: Omit<BasicFormProps, 'renderField'>, objectPath: ObjectPath, fields: FormField[]): BasicFormProps {
  const key = (name: string) => encodeFieldKey(objectPath, name);
  return {
    ...root,
    document: { ...root.document, form: { groups: [{ id: 'resource-values', label: '', locked: true,
      defaultExpanded: true, capability: false, enabled: true, fields, addableFields: [] }], addableGroups: [] } },
    drafts: scopedFields(root.drafts, objectPath, fields), errors: scopedFields(root.errors, objectPath, fields),
    onDraft: (name, text) => root.onDraft(key(name), text), onCommit: name => root.onCommit(key(name)),
    onReset: name => root.onReset(key(name)), onComposition: (name, active) => root.onComposition(key(name), active),
    onLoadReference: (name, query) => root.onLoadReference(key(name), query),
    onAction: async (action, payload) => {
      if (action !== 'set_field') throw new Error('此资源字段不支持该操作。');
      await root.onAction('resource_set', { ...payload, objectPath });
    },
  };
}

/** Lookup includes resource leaves nested inside ordinary objects and arrays. */
export function findResourceField(plan: NestedFormPlan, key: string): FormField | undefined {
  const address = decodeFieldKey(key);
  const target = JSON.stringify(address.objectPath);
  const at = (path: ObjectPath, fields: FormField[]) => JSON.stringify(path) === target
    ? fields.find(field => field.name === address.field) : undefined;
  const resource = (field: ResourceDescriptor): FormField | undefined => {
    if (field.control === 'resource_list') {
      for (const row of field.rows) { const found = at(row.objectPath, row.fields); if (found) return found; }
    } else if (field.control === 'resource_slot') return at(field.objectPath, field.fields);
    else for (const child of field.children) {
      const found = isResourceField(child) ? resource(child) : at(field.objectPath, [child]);
      if (found) return found;
    }
    return undefined;
  };
  const visit = (node: NestedFormPlan): FormField | undefined => {
    for (const field of node.groups.flatMap(group => group.fields)) {
      if (isResourceField(field)) { const found = resource(field); if (found) return found; }
      else if (field.control === 'object' && field.child) { const found = visit(field.child); if (found) return found; }
      else if (field.control === 'array') for (const item of field.items) {
        if (item.form) { const found = visit(item.form); if (found) return found; }
      }
    }
    return undefined;
  };
  return visit(plan);
}
