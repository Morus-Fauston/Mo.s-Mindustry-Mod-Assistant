export interface ContentTemplate { kind: string; label: string; group?: string }
export interface ContentCategory { id: string; label: string; templates: ContentTemplate[] }
export interface ContentCatalogue { namePattern: string; nameHint: string; categories: ContentCategory[] }
export type ContentAction = 'create_content' | 'rename_content' | 'delete_content' | 'reveal_content' | 'create_project';
export type ContentDialog = Exclude<ContentAction, 'reveal_content'>;
export interface ContentToolsProps {
  sessionId: string | null;
  activePath: string | null;
  disabled: boolean;
  completionId?: string;
  recovery?: boolean;
  recoveryBusy?: boolean;
  onRecover?: () => Promise<void>;
  loadCatalogue: () => Promise<ContentCatalogue>;
  onAction: (action: ContentAction, payload: Record<string, unknown>) => Promise<void>;
}

export interface ContentForm {
  category: string;
  kind: string;
  name: string;
  modId: string;
  displayName: string;
  author: string;
}

export interface ContentToolsSnapshot {
  sessionId: string | null;
  mode: ContentDialog | null;
  targetPath: string | null;
  catalogue: ContentCatalogue | null;
  loading: boolean;
  submitting: boolean;
  error: string;
  conflict: boolean;
  form: ContentForm;
}
