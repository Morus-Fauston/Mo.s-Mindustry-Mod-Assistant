/** Diagnostics come from the Python session, never from a second UI validator. */
export interface ValidationIssue {
  id: string;
  severity: 'error' | 'warning';
  message: string;
  path: string | null;
  field: string | null;
  objectPath?: (string | number)[];
  line?: number;
  column?: number;
  target: 'form' | 'source' | 'file' | 'unavailable';
  origin: 'project' | 'content' | 'source';
}

export interface ValidationReport {
  sessionId: string;
  revision: number;
  issues: ValidationIssue[];
  errors: number;
  warnings: number;
  complete: boolean;
}
