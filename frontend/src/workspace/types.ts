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
  warnings?: string[];
}

interface DocumentCommon {
  sessionId: string;
  path: string;
  name: string;
  category: string;
  contentType: string;
  fieldNames: Record<string, string>;
  fieldDocs: Record<string, string>;
  revision: number;
  dirty: boolean;
  sourceText?: string;
  sourceError?: { message: string; line?: number; column?: number } | null;
}

export interface ValidDocumentSnapshot extends DocumentCommon {
  validData?: true;
  data: Record<string, unknown>;
  form: FormPlan;
}
export interface RawDocumentSnapshot extends DocumentCommon {
  validData: false;
  data: null;
  form: null;
  sourceText: string;
  sourceError: { message: string; line?: number; column?: number };
}
export type DocumentSnapshot = ValidDocumentSnapshot | RawDocumentSnapshot;

export interface EditingState {
  sessionId: string | null;
  revision: number;
  documents: DocumentSnapshot[];
  history: { canUndo: boolean; canRedo: boolean; undoDescription: string; redoDescription: string };
  autoSaveInterval: number;
  closeApproved?: boolean;
}

export interface RecentProject { path: string; name: string }
