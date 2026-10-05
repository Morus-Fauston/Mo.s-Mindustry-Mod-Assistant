import type { FormField, FormGroup, FormPlan } from '../forms/types';

export type ObjectSegment = string | { itemId: string };
export type ObjectPath = ObjectSegment[];
export interface NestedObjectField extends Omit<FormField, 'control'> {
  control: 'object';
  child?: NestedFormPlan;
  canCreate: boolean;
}
export interface NestedArrayItem {
  itemId: string;
  index: number;
  form?: NestedFormPlan;
  field?: FormField;
  notice?: string;
}
export interface NestedArrayField extends Omit<FormField, 'control'> {
  control: 'array';
  items: NestedArrayItem[];
  canInsert: boolean;
  canRemove: boolean;
  canMove: boolean;
}
export type NestedField = FormField | NestedObjectField | NestedArrayField;
export interface NestedFormGroup extends Omit<FormGroup, 'fields'> { fields: NestedField[] }
export interface NestedFormPlan extends Omit<FormPlan, 'groups'> {
  groups: NestedFormGroup[];
  objectPath: ObjectPath;
  contentType: string;
  knownType: boolean;
  notice?: string;
  typeSelector?: { value: string | null; choices: { value: string; label: string }[] };
}
