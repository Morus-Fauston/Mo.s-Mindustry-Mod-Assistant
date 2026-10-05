import type { FormDrafts, FormField } from './types';

export function fieldText(field: FormField, drafts: FormDrafts): string {
  if (Object.hasOwn(drafts, field.name)) return drafts[field.name];
  if (field.displayValue === null || field.displayValue === undefined) return '';
  return typeof field.displayValue === 'object' ? JSON.stringify(field.displayValue) : String(field.displayValue);
}

export function fieldHint(field: FormField): string {
  const state = !field.present ? '未写入文件，当前仅显示缺省值。'
    : field.value === null ? '已写入文件：显式空值（null）。'
      : JSON.stringify(field.value) === JSON.stringify(field.defaultValue) ? '已写入文件，值与默认值相同。' : '已写入文件。';
  return [field.help, state, !field.present && field.defaultSource ? `缺省来源：${field.defaultSource}` : '',
    field.readOnly ? '此字段只读。' : '', field.inactiveReason].filter(Boolean).join('\n');
}

export function shouldCommitKey(key: string, composing: boolean, multiline: boolean, modifier: boolean, keyCode: number): boolean {
  return key === 'Enter' && !composing && keyCode !== 229 && (!multiline || modifier);
}
