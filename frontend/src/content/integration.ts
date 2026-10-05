import type { ContentAction } from './types';
import type { EditingState, ProjectSnapshot, TreeNode } from '../workspace/types';

export interface ContentChange {
  action: 'create' | 'rename' | 'delete'; beforePath: string | null; afterPath: string | null; undo: boolean;
}
export interface ContentResult {
  state?: EditingState; project?: ProjectSnapshot | null; tree?: TreeNode[];
  change?: ContentChange | null; contentChange?: ContentChange | null;
  activePath?: string | null; cancelled?: boolean;
}
type Views = Record<string, { mode: 'form' | 'source'; seen: boolean }>;

export function reconcileContentViews(previous: Views, change: ContentChange | null,
    paths: string[], rawPaths: string[] = []): Views {
  const next = { ...previous };
  if (change?.action === 'rename') {
    const from = change.undo ? change.afterPath : change.beforePath;
    const to = change.undo ? change.beforePath : change.afterPath;
    if (from && to && from !== to) { if (next[from]) next[to] = next[from]; delete next[from]; }
  }
  for (const path of rawPaths) next[path] = { mode: 'source', seen: true };
  return Object.fromEntries(Object.entries(next).filter(([path]) => paths.includes(path)));
}

export function affectedContentPaths(action: ContentAction, payload: Record<string, unknown>, paths: string[]): string[] {
  if (action === 'reveal_content') return [];
  if (action === 'create_project') return paths;
  if (action === 'create_content') return [`content/${payload.category}/${payload.name}.json`];
  return typeof payload.path === 'string' ? [payload.path] : [];
}
