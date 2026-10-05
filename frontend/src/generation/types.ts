import type { SpriteTarget } from '../resources/types';

export type GenerationSuffix = '-outline' | '-shadow' | '-full';
export interface GenerationOutput { suffix: string; options?: Record<string, unknown> }
export interface GenerationCandidate {
  sessionId: string;
  candidateId: string;
  outputs: (SpriteTarget & { width: number; height: number; dataUrl: string })[];
}
export interface GenerationCallbacks {
  onPreview: (outputs: GenerationOutput[]) => Promise<GenerationCandidate>;
  onConfirm: (candidateId: string, overwrite: boolean) => Promise<void>;
  onCancel: (candidateId: string) => Promise<void>;
}
export interface GenerationParameters { expandPx: string; color: string; opacity: string }
export const defaultParameters: GenerationParameters = { expandPx: '1', color: '#000000', opacity: '80' };
export const parameterKeys = { expandPx: 'spriteGenerationExpandPx', color: 'spriteGenerationColor', opacity: 'spriteGenerationOpacity' } as const;

export function supportedTargets(targets: SpriteTarget[]): SpriteTarget[] {
  const seen = new Set<string>();
  return targets.filter(target => {
    if (!['-outline', '-shadow', '-full'].includes(target.suffix) || seen.has(target.suffix)) return false;
    seen.add(target.suffix); return true;
  });
}

export function generationParametersError(selected: string[], values: GenerationParameters): Partial<Record<keyof GenerationParameters, string>> {
  const errors: Partial<Record<keyof GenerationParameters, string>> = {};
  if (selected.includes('-outline')) {
    if (!/^\d+$/.test(values.expandPx.trim()) || Number(values.expandPx) > 8) errors.expandPx = '请输入 0 至 8 的整数。';
    if (!/^#?[0-9a-fA-F]{6}$/.test(values.color.trim())) errors.color = '请输入六位十六进制颜色。';
  }
  if (selected.includes('-shadow') && (!/^\d+$/.test(values.opacity.trim()) || Number(values.opacity) > 255)) errors.opacity = '请输入 0 至 255 的整数。';
  return errors;
}

export function generationOutputs(targets: SpriteTarget[], selected: string[], values: GenerationParameters): GenerationOutput[] {
  const supported = supportedTargets(targets).filter(target => selected.includes(target.suffix));
  if (!supported.length) throw new Error('请选择至少一种生成结果。');
  if (Object.keys(generationParametersError(supported.map(target => target.suffix), values)).length) throw new Error('请修正生成参数后重试。');
  return supported.map(target => ({ suffix: target.suffix, ...(target.suffix === '-outline'
    ? { options: { expandPx: Number(values.expandPx), color: values.color.trim() } }
    : target.suffix === '-shadow' ? { options: { opacity: Number(values.opacity) } } : {}) }));
}
