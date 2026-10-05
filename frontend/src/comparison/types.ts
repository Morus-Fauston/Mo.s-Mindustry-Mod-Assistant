export interface SourceDescriptor {
  sourceId: string;
  kind: 'vanilla' | 'folder' | 'zip';
  label: string;
  categories: { id: string; label: string }[];
  warnings: string[];
}

export interface ReferenceSelection { sourceId: string; category: string; name: string }
export interface CandidatePage {
  sourceId: string;
  category: string;
  candidates: (ReferenceSelection & { label: string })[];
  offset: number;
  total: number;
  hasMore: boolean;
}
export type ValueKind = 'missing' | 'null' | 'boolean' | 'number' | 'string' | 'array' | 'object' | 'nonfinite';
export interface ComparisonCell { present: boolean; kind: ValueKind; text: string; truncated: boolean }
export interface Comparison extends ReferenceSelection {
  sessionId: string;
  currentPath: string;
  revision: number;
  rows: { field: string; current: ComparisonCell; reference: ComparisonCell; different: boolean }[];
}
export interface ComparisonCallbacks {
  onOpen: (kind: 'folder' | 'zip') => Promise<SourceDescriptor | null>;
  onSources: () => Promise<{ sources: SourceDescriptor[] }>;
  onCandidates: (sourceId: string, category: string, query: string, offset?: number) => Promise<CandidatePage>;
  onCompare: (sourceId: string, category: string, name: string) => Promise<Comparison>;
  onRelease: (sourceId: string) => Promise<void>;
}

export const valueKindLabels: Record<ValueKind, string> = {
  missing: '未设置', null: '空值', boolean: '布尔值', number: '数字', string: '文本',
  array: '列表', object: '对象', nonfinite: '非有限数字',
};
