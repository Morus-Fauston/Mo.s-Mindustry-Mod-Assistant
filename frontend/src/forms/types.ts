export interface FormField {
  name: string;
  label: string;
  help: string;
  javaType: string;
  mode: string;
  control: 'number' | 'string' | 'boolean' | 'color' | 'readonly';
  fieldType: string;
  nullable: boolean;
  readOnly: boolean;
  deletable: boolean;
  present: boolean;
  value: unknown;
  displayValue: unknown;
  defaultValue: unknown;
  defaultSource: string;
  inactiveReason: string;
  validationError: string;
  swatchHex?: string;
  minimum?: number;
  integer?: boolean;
}

export interface FormGroup {
  id: string;
  label: string;
  locked: boolean;
  defaultExpanded: boolean;
  capability: boolean;
  enabled: boolean;
  fields: FormField[];
  addableFields: { name: string; label: string }[];
}

export interface FormPlan {
  groups: FormGroup[];
  addableGroups: { id: string; label: string }[];
}

export type FormDrafts = Record<string, string>;
export type FormErrors = Record<string, string>;
