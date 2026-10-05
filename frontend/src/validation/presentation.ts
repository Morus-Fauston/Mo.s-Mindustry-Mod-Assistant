import type { ValidationIssue, ValidationReport } from './types';

export type ReportStatus = 'empty' | 'current' | 'stale' | 'foreign';

export function reportStatus(report: ValidationReport | null, sessionId: string | null, revision: number | null): ReportStatus {
  if (!report) return 'empty';
  if (report.sessionId !== sessionId) return 'foreign';
  return report.revision === revision ? 'current' : 'stale';
}

export function issueLocation(issue: ValidationIssue, status: ReportStatus): { enabled: boolean; label: string; notice: string } {
  if (status === 'foreign') return { enabled: false, label: '无法定位', notice: '报告属于之前的工程，请重新校验。' };
  if (!issue.path || issue.target === 'unavailable') return { enabled: false, label: '无法定位', notice: '暂无可打开位置。' };
  if (status === 'stale') return { enabled: true, label: '打开文件', notice: '报告已过期，仅打开文件；请重新校验后定位字段。' };
  if (issue.target === 'form' && issue.field) return { enabled: true, label: '定位字段', notice: '' };
  if (issue.target === 'source') {
    const hasLine = Number.isInteger(issue.line) && issue.line! > 0;
    return { enabled: true, label: hasLine ? '定位源码' : '打开源码', notice: hasLine ? '' : '未提供精确位置，仅打开源码。' };
  }
  return { enabled: true, label: '打开文件', notice: '未提供精确位置，仅打开文件。' };
}

export function sourcePosition(issue: ValidationIssue): string {
  if (!Number.isInteger(issue.line) || issue.line! < 1) return '';
  return `第 ${issue.line} 行${Number.isInteger(issue.column) && issue.column! > 0 ? `，第 ${issue.column} 列` : ''}`;
}
