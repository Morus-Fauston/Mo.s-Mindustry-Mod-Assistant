import type { FormField } from '../forms/types';
import type { ObjectPath } from '../nested/types';

export interface ResearchRow {
  itemId: string;
  objectPath: ObjectPath;
  fields: FormField[];
  value: unknown;
  notice?: string;
  typeSelector?: { value: string | null; choices: { value: string; label: string }[] };
}

export interface ResearchCollection {
  name: string;
  label: string;
  help: string;
  objectPath: ObjectPath;
  rows: ResearchRow[];
  readOnly: boolean;
  validationError: string;
  canInsert: boolean;
  canRemove: boolean;
  canMove: boolean;
  value?: unknown;
}

interface ResearchBase extends Omit<FormField, 'control'> { objectPath: ObjectPath }
export interface ResearchDescriptor extends ResearchBase {
  control: 'research';
  fields: FormField[];
  requirements?: ResearchCollection;
  objectives?: ResearchCollection;
}
export interface PlanetSetDescriptor extends ResearchBase {
  control: 'planet_set';
  rows: ResearchRow[];
  canInsert?: boolean;
  canRemove?: boolean;
  canMove?: boolean;
  addField?: FormField;
}
export type ResearchSpecialField = ResearchDescriptor | PlanetSetDescriptor;

export function isResearchField(value: unknown): value is ResearchSpecialField {
  return value !== null && typeof value === 'object' && 'control' in value
    && (value.control === 'research' || value.control === 'planet_set');
}
