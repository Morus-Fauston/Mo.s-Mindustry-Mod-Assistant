import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { ValidationReportPanel, type ValidationReportPanelProps } from './ValidationReportPanel';
import { issueLocation, reportStatus } from './presentation';
import type { ValidationIssue, ValidationReport } from './types';

const issue = (extra: Partial<ValidationIssue> = {}): ValidationIssue => ({ id: 'block-health', severity: 'error',
  message: '生命值必须为数字。', path: 'content/blocks/wall.json', field: 'health', target: 'form', origin: 'content', ...extra });
const report = (extra: Partial<ValidationReport> = {}): ValidationReport => ({ sessionId: 'current', revision: 7,
  issues: [issue(), issue({ id: 'unit-health', path: 'content/units/wall.json', severity: 'warning', message: '缺少主贴图。', target: 'file' })],
  errors: 1, warnings: 1, complete: true, ...extra });
const props = (extra: Partial<ValidationReportPanelProps> = {}): ValidationReportPanelProps => ({ report: report(),
  currentSessionId: 'current', currentRevision: 7, busy: false, error: '', onValidate: vi.fn(async () => {}), onLocate: vi.fn(), ...extra });
const render = (input: ValidationReportPanelProps) => renderToStaticMarkup(createElement(ValidationReportPanel, input));

describe('校验报告只读展示', () => {
  it('区分错误警告并保留同名文件的完整分类身份，渲染无业务动作', () => {
    const input = props(), html = render(input);
    expect(html).toContain('错误 1 项'); expect(html).toContain('警告 1 项');
    expect(html).toContain('content/blocks/wall.json'); expect(html).toContain('content/units/wall.json');
    expect(html).toContain('生命值必须为数字。'); expect(html).toContain('缺少主贴图。');
    expect(html).toContain('定位字段'); expect(html).toContain('未提供精确位置');
    expect(input.onValidate).not.toHaveBeenCalled(); expect(input.onLocate).not.toHaveBeenCalled();
  });

  it('同会话过期报告只展示打开文件动作，跨会话禁定位', () => {
    const stale = render(props({ currentRevision: 8 }));
    expect(stale).toContain('报告已过期'); expect(stale).toContain('仅打开文件');
    expect(stale).not.toMatch(/<button[^>]*>定位字段<\/button>/);
    const previous = render(props({ currentSessionId: 'next' }));
    expect(previous).toContain('报告属于之前的工程');
    expect(previous).not.toContain('定位字段');
    expect(issueLocation(issue(), 'foreign').enabled).toBe(false);
  });

  it('未完成、失败和空报告不宣称通过，完成的空报告才显示未发现问题', () => {
    expect(render(props({ report: null }))).toContain('尚未校验');
    const incomplete = render(props({ report: report({ issues: [], errors: 0, warnings: 0, complete: false }) }));
    expect(incomplete).toContain('校验未完成'); expect(incomplete).not.toContain('未发现问题');
    const failed = render(props({ report: report({ issues: [], errors: 0, warnings: 0 }), error: '读取工程失败。' }));
    expect(failed).toContain('读取工程失败。'); expect(failed).not.toContain('未发现问题');
    expect(render(props({ report: report({ issues: [], errors: 0, warnings: 0 }) }))).toContain('本次校验未发现问题');
    expect(render(props({ report: report({ issues: [] }) }))).not.toContain('未发现问题');
  });

  it('工程信息与无位置问题明确不可定位，源码只显示真实行列', () => {
    const input = props({ report: report({ issues: [issue({ path: 'mod.json', target: 'unavailable', field: null }),
      issue({ id: 'raw', target: 'source', origin: 'source', field: null, line: 3, column: 4 }),
      issue({ id: 'unknown', path: null, target: 'unavailable', field: null })] }) });
    const html = render(input);
    expect(html).toContain('工程信息文件（mod.json）'); expect(html).toContain('暂无可打开位置');
    expect(html).toContain('第 3 行，第 4 列');
    expect(issueLocation(issue({ target: 'source', field: null }), 'current').label).toBe('打开源码');
    expect(issueLocation(issue({ path: null }), 'current').enabled).toBe(false);
  });

  it('重新校验与定位受忙碌状态控制，未打开工程时不可校验', () => {
    const html = render(props({ busy: true }));
    expect(html).toContain('aria-busy="true"'); expect(html).toContain('校验中');
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>校验中/);
    expect(render(props({ currentSessionId: null, report: null }))).toContain('请先打开工程');
  });

  it('报告状态仅取会话及修订身份，未伪造业务规则', () => {
    expect(reportStatus(null, 'current', 7)).toBe('empty');
    expect(reportStatus(report(), 'current', 7)).toBe('current');
    expect(reportStatus(report(), 'current', 8)).toBe('stale');
    expect(reportStatus(report(), null, 7)).toBe('foreign');
  });
});
