import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { encodeFieldKey } from '../nested/address';
import type { FormField } from '../forms/types';
import type { BasicFormProps } from '../forms/BasicForm';
import { findResearchField, researchLeafProps } from './address';
import { ResearchField } from './ResearchField';
import type { PlanetSetDescriptor, ResearchCollection, ResearchDescriptor } from './types';
import type { NestedField, NestedFormPlan } from '../nested/types';

const amount: FormField = { name: 'amount', label: '数值', help: '需求数量', javaType: 'int', mode: 'PRIMITIVE',
  control: 'number', fieldType: 'num', integer: true, nullable: false, readOnly: false, deletable: false,
  present: true, value: 2, displayValue: 2, defaultValue: 1, defaultSource: '', inactiveReason: '', validationError: '' };

function root(): Omit<BasicFormProps, 'renderField'> {
  return { document: { sessionId: 'session', path: 'content/blocks/wall.json', name: 'wall', category: 'blocks',
    contentType: 'Wall', data: {}, fieldNames: { type: '类型' }, fieldDocs: {}, revision: 1, dirty: false, form: { groups: [], addableGroups: [] } },
    disabled: false, drafts: {}, errors: {}, onDraft: vi.fn(), onCommit: vi.fn(async () => {}), onReset: vi.fn(),
    onComposition: vi.fn(), onAction: vi.fn(async () => {}),
    onLoadReference: vi.fn(async () => ({ candidates: [], categories: [], current: { value: null, label: '未选择', known: true } })) };
}

const itemId = 'a'.repeat(32);
const reference: FormField = { ...amount, name: 'parent', label: '父节点', control: 'reference', fieldType: 'ref',
  javaType: 'String', mode: 'STRING_REF', value: 'copper-wall', displayValue: 'copper-wall', nullable: true };
function collection(name: 'requirements' | 'objectives'): ResearchCollection {
  return { name, label: name === 'requirements' ? '建造需求' : '研究目标', help: '', objectPath: ['research', name],
    readOnly: false, validationError: '', canInsert: true, canRemove: true, canMove: false,
    rows: [{ itemId, objectPath: ['research', name, { itemId }], fields: name === 'requirements' ? [amount] : [], value: {} }] };
}
function research(): ResearchDescriptor {
  return { ...reference, name: 'research', label: '研究', control: 'research', objectPath: ['research'], fields: [reference],
    requirements: collection('requirements'), objectives: collection('objectives') };
}
function planets(): PlanetSetDescriptor {
  const planet = { ...reference, name: 'planet', label: '星球', nullable: false, value: 'missing-planet', displayValue: 'missing-planet' };
  return { ...reference, name: 'shownPlanets', label: '显示星球', control: 'planet_set', objectPath: ['shownPlanets'],
    canInsert: true, canRemove: true, rows: [{ itemId, objectPath: ['shownPlanets', { itemId }], fields: [planet], value: 'missing-planet' }],
    addField: { ...planet, present: false, value: null, displayValue: '' } };
}
function plan(field: ResearchDescriptor | PlanetSetDescriptor): NestedFormPlan {
  return { objectPath: [], contentType: 'Wall', knownType: true, addableGroups: [], groups: [{ id: 'test', label: '测试', locked: true,
    defaultExpanded: true, capability: false, enabled: true, fields: [field as unknown as NestedField], addableFields: [] }] };
}

describe('研究字段地址', () => {
  it('需求所有输入回调使用完整稳定地址，实际修改走research_set', async () => {
    const props = root(), path = ['research', 'requirements', { itemId: 'a'.repeat(32) }];
    const leaf = researchLeafProps(props, path, [amount]);
    const key = encodeFieldKey(path, 'amount');
    leaf.onDraft('amount', '1e-'); await leaf.onCommit('amount'); leaf.onReset('amount'); leaf.onComposition('amount', true);
    await leaf.onLoadReference('item', '铜'); await leaf.onAction('set_field', { field: 'amount', value: 999999 });
    expect(props.onDraft).toHaveBeenCalledWith(key, '1e-');
    expect(props.onCommit).toHaveBeenCalledWith(key);
    expect(props.onReset).toHaveBeenCalledWith(key);
    expect(props.onComposition).toHaveBeenCalledWith(key, true);
    expect(props.onLoadReference).toHaveBeenCalledWith(encodeFieldKey(path, 'item'), '铜');
    expect(props.onAction).toHaveBeenCalledWith('research_set', { objectPath: path, field: 'amount', value: 999999 });
  });
  it('只读未知根形状展示原值且不会访问缺失的研究集合或提交', () => {
    const props = root();
    const field: ResearchDescriptor = { ...amount, name: 'research', label: '研究', control: 'research',
      objectPath: ['research'], readOnly: true, fields: [], displayValue: ['unknown-shape'], validationError: '研究配置格式无效，原值已保留。' };
    const html = renderToStaticMarkup(createElement(ResearchField, { ...props, field, objectPath: [] }));
    expect(html).toContain('unknown-shape'); expect(html).toContain('研究配置格式无效');
    expect(html).toContain('aria-invalid="true"'); expect(props.onAction).not.toHaveBeenCalled();
  });
  it('星球引用提交映射到原数组owner和itemId，候选读取仍用叶子地址', async () => {
    const props = root(), field = planets(), row = field.rows[0];
    const leaf = researchLeafProps(props, row.objectPath, row.fields, { objectPath: [], field: field.name, itemId });
    await leaf.onAction('set_field', { field: 'planet', value: 'serpulo' });
    expect(props.onAction).toHaveBeenCalledWith('planet_set', { objectPath: [], field: 'shownPlanets', itemId, value: 'serpulo' });
    await leaf.onLoadReference('planet', '赛普罗');
    expect(props.onLoadReference).toHaveBeenCalledWith(encodeFieldKey(row.objectPath, 'planet'), '赛普罗');
    await expect(leaf.onAction('set_field', { field: 'planet', value: null })).rejects.toThrow('星球');
    await expect(leaf.onAction('delete_field', { field: 'planet' })).rejects.toThrow('不支持');
  });
  it('需求草稿及错误留在稳定行，未知目标显示原值且仍可显式选择五种类型', () => {
    const props = root(), field = research();
    const row = field.objectives!.rows[0];
    row.value = { type: 'Unknown', keep: 3 }; row.notice = '未识别目标类型，原值已保留。';
    row.typeSelector = { value: 'Unknown', choices: [
      { value: 'Research', label: '研究内容' }, { value: 'Produce', label: '生产内容' },
      { value: 'SectorComplete', label: '完成战区' }, { value: 'OnSector', label: '位于战区' }, { value: 'OnPlanet', label: '位于星球' },
    ] };
    const key = encodeFieldKey(field.requirements!.rows[0].objectPath, 'amount');
    props.drafts = { [key]: '1e-' }; props.errors = { [key]: '请输入完整的整数需求数量。' };
    const html = renderToStaticMarkup(createElement(ResearchField, { ...props, field, objectPath: [] }));
    expect(html).toContain(`data-item-id="${itemId}"`); expect(html).toContain('value="1e-"');
    expect(html).toContain('请输入完整的整数需求数量。'); expect(html).toContain('未识别类型：Unknown');
    for (const choice of row.typeSelector.choices) expect(html).toContain(choice.label);
    expect(html).toContain('keep'); expect(html).toContain('添加研究目标');
    expect(props.onAction).not.toHaveBeenCalled(); expect(props.onDraft).not.toHaveBeenCalled();
  });
  it('七字段低频设置按已有值展开，字段名字和帮助均沿后端描述', () => {
    const props = root(), field = research();
    field.fields.push({ ...amount, name: 'name', label: '研究根名称', help: '研究根专用帮助', control: 'string', value: '根甲', displayValue: '根甲' });
    const html = renderToStaticMarkup(createElement(ResearchField, { ...props, field, objectPath: [] }));
    expect(html).toContain('研究根名称'); expect(html).toContain('研究根专用帮助');
    expect(html).toContain('value="根甲"'); expect(html).toContain('收起更多科技树设置');
  });
  it('星球未知值保留可见，新增使用统一选择器且读取本身不添加', () => {
    const props = root();
    const html = renderToStaticMarkup(createElement(ResearchField, { ...props, field: planets(), objectPath: [] }));
    expect(html).toContain('missing-planet'); expect(html).toContain('aria-label="添加星球"');
    expect(html).toContain('删除第 1 个星球'); expect(props.onAction).not.toHaveBeenCalled();
  });
  it('lookup识别七字段、两种列表及星球新增候选，删除旧itemId不再命中', () => {
    const field = research();
    expect(findResearchField(plan(field), encodeFieldKey(['research'], 'parent'))).toBe(reference);
    expect(findResearchField(plan(field), encodeFieldKey(field.requirements!.rows[0].objectPath, 'amount'))).toBe(amount);
    expect(findResearchField(plan(field), encodeFieldKey(['research', 'requirements', { itemId: 'b'.repeat(32) }], 'amount'))).toBeUndefined();
    const planet = planets();
    expect(findResearchField(plan(planet), encodeFieldKey(['shownPlanets'], 'planet'))).toBe(planet.addField);
    expect(findResearchField(plan(planet), encodeFieldKey(planet.rows[0].objectPath, 'planet'))).toBe(planet.rows[0].fields[0]);
  });
  it('集合错误形状只展示原值且不提供可写需求行', () => {
    const props = root(), field = research();
    field.requirements = { ...field.requirements!, readOnly: true, rows: [], value: 'copper/2', validationError: '列表格式无效，原值已保留。' };
    const html = renderToStaticMarkup(createElement(ResearchField, { ...props, field, objectPath: [] }));
    expect(html).toContain('copper/2'); expect(html).toContain('列表格式无效');
    expect(html).not.toContain('添加建造需求'); expect(props.onAction).not.toHaveBeenCalled();
  });
});
