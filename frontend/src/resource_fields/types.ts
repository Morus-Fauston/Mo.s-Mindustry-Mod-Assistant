import type { FormField } from '../forms/types';
import type { ObjectPath } from '../nested/types';

interface ResourceBase extends Omit<FormField, 'control'> { objectPath: ObjectPath }
export interface ResourceRow { itemId: string; objectPath: ObjectPath; fields: FormField[]; notice?: string }
export interface ResourceListField extends ResourceBase {
  control: 'resource_list'; resourceType?: 'item' | 'liquid'; rows: ResourceRow[];
  canInsert?: boolean; canRemove?: boolean; canMove?: boolean;
}
export interface ResourceSlotField extends ResourceBase {
  control: 'resource_slot'; resourceType?: 'item' | 'liquid'; fields: FormField[]; empty: boolean;
}
export interface ConsumesField extends ResourceBase {
  control: 'consumes'; children: (ResourceListField | ResourceSlotField | FormField)[];
  addable: { name: string; label: string }[];
}
export type ResourceDescriptor = ResourceListField | ResourceSlotField | ConsumesField;

export function isResourceField(value: unknown): value is ResourceDescriptor {
  return value !== null && typeof value === 'object' && 'control' in value
    && ['resource_list', 'resource_slot', 'consumes'].includes(String(value.control));
}
