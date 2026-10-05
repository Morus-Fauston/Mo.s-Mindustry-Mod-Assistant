import { useId, useRef, useState } from 'react';
import { issueLocation, reportStatus, sourcePosition } from './presentation';
import type { ValidationIssue, ValidationReport } from './types';
import styles from './ValidationReportPanel.module.css';

export interface ValidationReportPanelProps {
  report: ValidationReport | null;
  currentSessionId: string | null;
  currentRevision: number | null;
  busy: boolean;
  error: string;
  onValidate: () => Promise<void>;
  /** App checks the report identity again; stale reports may open only the file. */
  onLocate: (issue: ValidationIssue) => void;
}

export function ValidationReportPanel(props: ValidationReportPanelProps) {
  const { report, currentSessionId, currentRevision, busy, error, onLocate } = props;
  const id = useId(), pending = useRef(false), latestSession = useRef(currentSessionId);
  latestSession.current = currentSessionId;
  const [running, setRunning] = useState(false);
  const [localError, setLocalError] = useState<{ sessionId: string | null; message: string } | null>(null);
  const status = reportStatus(report, currentSessionId, currentRevision);
  const blocked = busy || running;
  const failure = error || (localError?.sessionId === currentSessionId ? localError.message : '');
  async function validate() {
    if (pending.current || busy || !currentSessionId) return;
    const owner = currentSessionId;
    pending.current = true; setRunning(true); setLocalError(null);
    try { await props.onValidate(); }
    catch (cause) {
      if (latestSession.current === owner) setLocalError({ sessionId: owner,
        message: cause instanceof Error ? cause.message : '校验未完成，请重试。' });
    } finally { pending.current = false; setRunning(false); }
  }
  return <section className={styles.panel} aria-labelledby={`${id}-title`} aria-busy={blocked}>
    <header className={styles.heading}>
      <h2 id={`${id}-title`}>校验报告</h2>
      <button type="button" className={styles.button} disabled={blocked || !currentSessionId} onClick={() => void validate()}>
        {blocked ? '校验中' : report ? '重新校验' : '校验工程'}
      </button>
    </header>
    {failure && <p className={styles.error} role="alert">{failure}</p>}
    {!currentSessionId && <p className={styles.notice}>请先打开工程。</p>}
    {status === 'foreign' && <p className={styles.notice} role="status">报告属于之前的工程，请重新校验。</p>}
    {status === 'stale' && <p className={styles.notice} role="status">报告已过期。问题位置可能已经变化，当前仅打开文件。</p>}
    {report && <>
      <div className={styles.summary} aria-label="校验问题总数">
        <span data-severity="error">错误 {report.errors} 项</span>
        <span data-severity="warning">警告 {report.warnings} 项</span>
      </div>
      {!report.complete && <p className={styles.error}>校验未完成，以下仅为已取得的问题，不能据此确认工程有效。</p>}
      {report.issues.length > 0 ? <ul className={styles.issues} aria-label="校验问题">
        {report.issues.map(issue => {
          const location = issueLocation(issue, status), position = sourcePosition(issue);
          return <li className={styles.issue} key={issue.id} data-validation-id={issue.id} data-severity={issue.severity}>
            <div className={styles.issueHeading}>
              <span className={styles.severity}>{issue.severity === 'error' ? '错误' : '警告'}</span>
              <button type="button" className={styles.locate} disabled={blocked || !location.enabled}
                title={location.notice || `${location.label}：${issue.path}`}
                aria-label={`${location.label}：${issue.path ?? '无位置'}，${issue.message}`}
                onClick={() => { if (!blocked && location.enabled) onLocate(issue); }}>{location.label}</button>
            </div>
            <p className={styles.message}>{issue.message}</p>
            <p className={styles.path}>{issue.path === 'mod.json' ? '工程信息文件（mod.json）' : issue.path ?? '未提供文件位置'}
              {position && <span className={styles.position}>{position}</span>}</p>
            {location.notice && <p className={styles.locationNotice}>{location.notice}</p>}
          </li>;
        })}
      </ul> : <p className={styles.notice}>{report.complete && report.errors === 0 && report.warnings === 0 && status === 'current' && !failure && !blocked
        ? '本次校验未发现问题。' : '此报告暂无问题条目。'}</p>}
    </>}
    {!report && <p className={styles.notice}>{blocked ? '正在读取当前工程并校验。' : '尚未校验。校验结果将列出错误、警告及可定位的文件。'}</p>}
  </section>;
}
