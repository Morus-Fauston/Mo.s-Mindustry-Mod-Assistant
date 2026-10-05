import type { BasicFormProps } from '../forms/BasicForm';
import type { FormField } from '../forms/types';
import { decodeFieldKey, encodeFieldKey, scopedFields } from '../nested/address';
import type { NestedFormPlan, ObjectPath } from '../nested/types';
import { isResearchField } from './types';

export interface PlanetTarget { objectPath: ObjectPath; field: string; itemId: string }

export function researchLeafProps(root: Omit<BasicFormProps, 'renderField'>, objectPath: ObjectPath,
  fields: FormField[], planet?: PlanetTarget): BasicFormProps {
  const key = (name: string) => encodeFieldKey(objectPath, name);
  return {
    ...root,
    document: { ...root.document, form: { groups: [{ id: 'research-values', label: '', locked: true,
      defaultExpanded: true, capability: false, enabled: true, fields, addableFields: [] }], addableGroups: [] } },
    drafts: scopedFields(root.drafts, objectPath, fields), errors: scopedFields(root.errors, objectPath, fields),
    onDraft: (name, text) => root.onDraft(key(name), text), onCommit: name => root.onCommit(key(name)),
    onReset: name => root.onReset(key(name)), onComposition: (name, active) => root.onComposition(key(name), active),
    onLoadReference: (name, query) => root.onLoadReference(key(name), query),
    onAction: async (action, payload) => {
      if (action !== 'set_field') throw new Error('此研究字段不支持该操作。');
      if (planet) {
        if (payload.field !== 'planet' || typeof payload.value !== 'string' || !payload.value) throw new Error('请选择有效的星球。');
        await root.onAction('planet_set', { ...planet, value: payload.value });
      } else await root.onAction('research_set', { ...payload, objectPath });
    },
  };
}

/** Includes the read-only candidate route for explicitly adding a planet. */
export function findResearchField(plan: NestedFormPlan, key: string): FormField | undefined {
  const address = decodeFieldKey(key), target = JSON.stringify(address.objectPath);
  const at = (path: ObjectPath, fields: FormField[]) => JSON.stringify(path) === target
    ? fields.find(field => field.name === address.field) : undefined;
  const visit = (node: NestedFormPlan): FormField | undefined => {
    for (const field of node.groups.flatMap(group => group.fields)) {
      const special: unknown = field;
      if (isResearchField(special)) {
        if (special.control === 'research') {
          const found = at(special.objectPath, special.fields); if (found) return found;
          for (const collection of [special.requirements, special.objectives]) for (const row of collection?.rows ?? []) {
            const leaf = at(row.objectPath, row.fields); if (leaf) return leaf;
          }
        } else {
          const add = special.addField && at(special.objectPath, [special.addField]); if (add) return add;
          for (const row of special.rows) { const leaf = at(row.objectPath, row.fields); if (leaf) return leaf; }
        }
      } else if (field.control === 'object' && field.child) { const found = visit(field.child); if (found) return found; }
      else if ((field.control === 'array' || field.control === 'weapon_array')) for (const item of field.items) {
        if (item.form) { const found = visit(item.form); if (found) return found; }
      }
    }
    return undefined;
  };
  return visit(plan);
}
