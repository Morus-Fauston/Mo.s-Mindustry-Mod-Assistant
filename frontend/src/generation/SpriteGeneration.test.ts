import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { SpriteGeneration, type SpriteGenerationProps } from './SpriteGeneration';
import { defaultParameters, generationOutputs, generationParametersError, supportedTargets } from './types';

const targets = [
  { suffix: '', label: '主体', path: 'sprites/units/unit.png', exists: true },
  { suffix: '-outline', label: '轮廓', path: 'sprites/units/unit-outline.png', exists: false },
  { suffix: '-shadow', label: '阴影', path: 'sprites/units/unit-shadow.png', exists: true },
  { suffix: '-full', label: '完整图', path: 'sprites/units/unit-full.png', exists: false },
  { suffix: '-cell', label: '细胞', path: 'sprites/units/unit-cell.png', exists: false },
];

describe('生成面板与现有参数', () => {
  it('只显示实际支持的三个派生层，参数显示名来自配置，重建不生成或写盘', () => {
    const props: SpriteGenerationProps = { sessionId: '甲', path: 'content/units/unit.json', revision: 1, disabled: false, targets,
      fieldNames: { spriteGenerationExpandPx: '测试描边宽度', spriteGenerationColor: '测试描边颜色', spriteGenerationOpacity: '测试阴影透明度' },
      fieldDocs: { spriteGenerationExpandPx: '现有生成器宽度参数说明。' },
      onPreview: vi.fn(), onConfirm: vi.fn(), onCancel: vi.fn() };
    const html = renderToStaticMarkup(createElement(SpriteGeneration, props));
    expect(html).toContain('轮廓'); expect(html).toContain('阴影'); expect(html).toContain('完整图');
    expect(html).not.toContain('细胞'); expect(html).not.toContain('主体');
    expect(html).toContain('测试描边宽度'); expect(html).toContain('现有生成器宽度参数说明。');
    expect(html).toContain('value="1"'); expect(html).toContain('value="#000000"');
    expect(props.onPreview).not.toHaveBeenCalled(); expect(props.onConfirm).not.toHaveBeenCalled(); expect(props.onCancel).not.toHaveBeenCalled();
  });

  it('默认参数严格等于旧生成器，仅支持目标会进入请求，完整图不附加参数', () => {
    expect(generationOutputs(targets, targets.map(target => target.suffix), defaultParameters)).toEqual([
      { suffix: '-outline', options: { expandPx: 1, color: '#000000' } },
      { suffix: '-shadow', options: { opacity: 80 } }, { suffix: '-full' },
    ]);
    expect(supportedTargets([...targets, targets[1]])).toHaveLength(3);
    expect(() => generationOutputs(targets, ['-cell'], defaultParameters)).toThrow('请选择');
  });

  it('空白、小数、指数和超范围整数均拒绝，零参数按零保留', () => {
    for (const value of ['', '1.5', '1e1', '-1', '9', 'Infinity']) {
      expect(generationParametersError(['-outline'], { ...defaultParameters, expandPx: value }).expandPx).toBeTruthy();
    }
    for (const value of ['', '1.5', '256', '-1', 'NaN']) {
      expect(generationParametersError(['-shadow'], { ...defaultParameters, opacity: value }).opacity).toBeTruthy();
    }
    expect(generationParametersError(['-outline'], { ...defaultParameters, color: '#00000000' }).color).toBeTruthy();
    expect(generationOutputs(targets, ['-outline', '-shadow'], { expandPx: '0', color: 'AABBCC', opacity: '0' })).toEqual([
      { suffix: '-outline', options: { expandPx: 0, color: 'AABBCC' } }, { suffix: '-shadow', options: { opacity: 0 } },
    ]);
    expect(generationOutputs(targets, ['-full'], { expandPx: '', color: '', opacity: '' })).toEqual([{ suffix: '-full' }]);
  });
});
