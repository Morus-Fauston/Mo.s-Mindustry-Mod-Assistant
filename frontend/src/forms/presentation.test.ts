import { describe, expect, it } from 'vitest';
import { fieldHint, fieldText, shouldCommitKey } from './presentation';
import type { FormField } from './types';

const field: FormField = { name: 'health', label: '生命值', help: '单位生命值。', javaType: 'float', mode: 'PRIMITIVE',
  control: 'number', fieldType: 'num', nullable: false, readOnly: false, deletable: false,
  present: false, value: null, displayValue: 100, defaultValue: 100, defaultSource: '元数据', inactiveReason: '', validationError: '' };

describe('表单展示语义', () => {
  it('区分缺省、显式默认与显式空值，草稿不被数值转换', () => {
    expect(fieldText(field, {})).toBe('100');
    expect(fieldText(field, { health: '1e-' })).toBe('1e-');
    expect(fieldHint(field)).toContain('未写入文件');
    expect(fieldHint({ ...field, present: true, value: 100 })).toContain('已写入文件');
    expect(fieldHint({ ...field, present: true, value: null, displayValue: null })).toContain('显式空值');
    expect(fieldText({ ...field, present: true, value: null, displayValue: null }, {})).toBe('');
  });
  it('中文组合输入不提交，多行说明仅Ctrl+Enter提交', () => {
    expect(shouldCommitKey('Enter', true, false, false, 13)).toBe(false);
    expect(shouldCommitKey('Enter', false, false, false, 229)).toBe(false);
    expect(shouldCommitKey('Enter', false, false, false, 13)).toBe(true);
    expect(shouldCommitKey('Enter', false, true, false, 13)).toBe(false);
    expect(shouldCommitKey('Enter', false, true, true, 13)).toBe(true);
  });
});
