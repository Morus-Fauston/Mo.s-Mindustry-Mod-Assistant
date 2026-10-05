import type { FormPlan } from '../forms/types';

export interface TreeNode {
  id: string;
  kind: 'group' | 'content' | 'sprite';
  label: string;
  path?: string;
  name?: string;
  category?: string;
  contentType?: string;
  children?: TreeNode[];
  error?: string;
}

export interface ProjectSnapshot {
  sessionId: string;
  name: string;
  root: string;
  tree: TreeNode[];
}

export interface DocumentSnapshot {
  sessionId: string;
  path: string;
  name: string;
  category: string;
  contentType: string;
  data: Record<string, unknown>;
  fieldNames: Record<string, string>;
  fieldDocs: Record<string, string>;
  revision: number;
  dirty: boolean;
  form: FormPlan;
}

export interface EditingState {
  sessionId: string | null;
  revision: number;
  documents: DocumentSnapshot[];
  history: { canUndo: boolean; canRedo: boolean; undoDescription: string; redoDescription: string };
  autoSaveInterval: number;
  closeApproved?: boolean;
}

export interface RecentProject { path: string; name: string }
