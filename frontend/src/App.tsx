import { Fragment, useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { desktop, DesktopError, type BootstrapData } from './bridge/desktop';
import { ProjectTree } from './workspace/ProjectTree';
import type { DocumentSnapshot, ProjectSnapshot, RecentProject, TreeNode } from './workspace/types';
import styles from './App.module.css';
import { createEditingClient } from './editing/client';
import { CloseDecision, type CloseChoice } from './editing/CloseDecision';
import { PreviewPanel } from './preview/PreviewPanel';

type Startup = { phase: 'loading' } | { phase: 'ready'; data: BootstrapData } | { phase: 'error'; message: string };
type Opening = { action: string; payload: Record<string, unknown>; sessionId: string | null; requestId: string };
type CloseIntent = { kind: 'documents'; paths: string[] } | { kind: 'project'; path?: string } | { kind: 'window' };

const categoryLabels: Record<string, string> = {
  Units: '单位', UnitTypes: '单位', Blocks: '方块', Weapons: '武器', Bullets: '子弹',
  Items: '物品', Liquids: '液体', StatusEffects: '状态效果',
  Planets: '星球', Sectors: '战区', SectorPresets: '战区',
};

export function App() {
  const [startup, setStartup] = useState<Startup>({ phase: 'loading' });
  const [project, setProject] = useState<ProjectSnapshot | null>(null);
  const projectRef = useRef<ProjectSnapshot | null>(null);
  const [editing] = useState(() => createEditingClient(desktop));
  const editor = useSyncExternalStore(editing.subscribe, editing.getSnapshot);
  const documents = editor.state?.documents ?? [];
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const draftsRef = useRef(drafts);
  const committing = useRef<Promise<void> | null>(null);
  const [intent, setIntent] = useState<CloseIntent | null>(null);
  const intentRef = useRef<CloseIntent | null>(null);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionError, setDecisionError] = useState('');
  const [activePath, setActivePath] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [recent, setRecent] = useState<RecentProject[]>([]);
  const [busy, setBusy] = useState(false);
  const openingProject = useRef(false);
  const unresolvedOpen = useRef<Opening | null>(null);
  const [needsRecovery, setNeedsRecovery] = useState(false);
  const [notice, setNotice] = useState('');
  const [failure, setFailure] = useState('');
  const pendingReads = useRef(new Set<string>());
  const generation = useRef(0);
  const selection = useRef(0);
  const load = useCallback(() => {
    setStartup({ phase: 'loading' });
    void desktop.bootstrap().then(data => setStartup({ phase: 'ready', data }))
      .catch((error: unknown) => setStartup({ phase: 'error', message: error instanceof Error ? error.message : '程序连接失败，请重试。' }));
  }, []);
  useEffect(load, [load]);
  useEffect(() => {
    if (startup.phase !== 'ready') return;
    let alive = true;
    void desktop.request<{ recentProjects: RecentProject[] }>('recent_projects', {}, null)
      .then(data => { if (alive) setRecent(data.recentProjects); })
      .catch(() => { if (alive) setFailure('最近工程读取失败，仍可通过选择目录打开工程。'); });
    return () => { alive = false; };
  }, [startup.phase]);

  useEffect(() => {
    if (startup.phase === 'ready') void editing.refresh().catch(error => setFailure(message(error)));
  }, [startup.phase, editing]);

  function updateDrafts(next: Record<string, string>) { draftsRef.current = next; setDrafts(next); }

  async function flushDrafts() {
    if (committing.current) await committing.current;
    const task = (async () => {
      for (const [path, text] of Object.entries(draftsRef.current)) {
        const value = Number(text);
        if (!text.trim() || !Number.isFinite(value) || value < 0) throw new Error('请输入非负有限数值后再保存。');
        const current = editing.getSnapshot().state?.documents.find(document => document.path === path);
        if (!current) continue;
        if (current.data.health !== value) await editing.run('set_field', { path, field: 'health', value });
        if (draftsRef.current[path] === text) {
          const next = { ...draftsRef.current }; delete next[path]; updateDrafts(next);
        }
      }
    })();
    committing.current = task;
    try { await task; } finally { if (committing.current === task) committing.current = null; }
  }

  async function editAction(action: 'save_opened' | 'undo' | 'redo') {
    if (busy || intentRef.current || editor.uncertain) return;
    try {
      setFailure('');
      await flushDrafts();
      await editing.run(action);
      setNotice(action === 'save_opened' ? '已保存所有打开的内容' : action === 'undo' ? '已撤销' : '已重做');
    } catch (error) { setFailure(message(error)); }
  }

  function clearIntent() { intentRef.current = null; setIntent(null); setDecisionError(''); }

  async function executeIntent(target: CloseIntent, choice: CloseChoice) {
    if (choice === 'cancel') { clearIntent(); return; }
    setDecisionBusy(true);
    try {
      if (choice === 'save') await flushDrafts();
      if (target.kind === 'documents') {
        generation.current += 1;
        await editing.run('close_documents', { paths: target.paths, decision: choice });
        const next = { ...draftsRef.current };
        target.paths.forEach(path => { delete next[path]; });
        updateDrafts(next);
      } else if (target.kind === 'project') {
        if (choice === 'save') await editing.run('save_opened');
        clearIntent();
        await openProject(target.path, choice === 'discard');
      } else {
        await editing.run('close_window', { decision: choice });
      }
      clearIntent();
    } catch (error) { setDecisionError(message(error)); setFailure(message(error)); }
    finally { setDecisionBusy(false); }
  }

  async function requestIntent(target: CloseIntent) {
    if (intentRef.current || openingProject.current || unresolvedOpen.current || editing.getSnapshot().uncertain) return;
    if (committing.current) { try { await committing.current; } catch { /* Present discard/cancel for invalid input. */ } }
    if (editing.getSnapshot().busy) return;
    // Reconcile completed reads before closing, including responses still in flight.
    const state = await editing.refresh().catch(error => { setFailure(message(error)); return null; });
    if (!state) return;
    const dirty = state.documents.filter(document => document.dirty || document.path in draftsRef.current)
      .filter(document => target.kind !== 'documents' || target.paths.includes(document.path));
    if (dirty.length) { intentRef.current = target; setIntent(target); setDecisionError(''); }
    else await executeIntent(target, 'discard');
  }

  const handlers = useRef({ requestIntent, editAction });
  handlers.current = { requestIntent, editAction };
  useEffect(() => {
    const close = () => { void handlers.current.requestIntent({ kind: 'window' }); };
    const keys = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey || intentRef.current) return;
      const key = event.key.toLowerCase();
      if (key === 's' || key === 'z' || key === 'y') {
        event.preventDefault();
        void handlers.current.editAction(key === 's' ? 'save_opened' : key === 'y' || event.shiftKey ? 'redo' : 'undo');
      }
    };
    window.addEventListener('moma-close-request', close);
    window.addEventListener('keydown', keys);
    const ready = () => {
      const host = window as unknown as { pywebview?: { api?: { close_ready?: () => Promise<boolean> } } };
      void host.pywebview?.api?.close_ready?.();
    };
    ready();
    window.addEventListener('pywebviewready', ready);
    return () => { window.removeEventListener('moma-close-request', close); window.removeEventListener('keydown', keys); window.removeEventListener('pywebviewready', ready); };
  }, []);

  useEffect(() => {
    const interval = editor.state?.autoSaveInterval ?? 0;
    if (!project || interval <= 0) return;
    const timer = setInterval(() => {
      const snapshot = editing.getSnapshot();
      if (!snapshot.busy && !snapshot.uncertain && !intentRef.current &&
          (snapshot.state?.documents.some(document => document.dirty) || Object.keys(draftsRef.current).length)) {
        void handlers.current.editAction('save_opened');
      }
    }, interval * 1000);
    return () => clearInterval(timer);
  }, [project?.sessionId, editor.state?.autoSaveInterval, editing]);

  useEffect(() => {
    if (activePath && !documents.some(document => document.path === activePath)) {
      const next = documents.at(-1)?.path ?? null; setActivePath(next); setSelectedPath(next);
    } else if (!activePath && documents.length) setActivePath(documents.at(-1)!.path);
  }, [documents, activePath]);

  async function openProject(path?: string, discard = false) {
    if (openingProject.current) return;
    openingProject.current = true;
    setBusy(true);
    setFailure('');
    setNotice(path ? '正在打开工程…' : '请选择工程目录');
    generation.current += 1;
    const recovering = unresolvedOpen.current !== null;
    const operation: Opening = unresolvedOpen.current ?? {
      action: path ? 'open_project' : 'choose_project', payload: { ...(path ? { path } : {}),
        expectedRevision: editing.getSnapshot().state?.revision ?? 0, discard },
      sessionId: projectRef.current?.sessionId ?? null, requestId: crypto.randomUUID(),
    };
    unresolvedOpen.current = operation;
    try {
      const call = recovering ? desktop.recoverRequest : desktop.request;
      const result = await call<ProjectSnapshot | { cancelled: true }>(
        operation.action, operation.payload, operation.sessionId, operation.requestId);
      unresolvedOpen.current = null;
      setNeedsRecovery(false);
      if ('cancelled' in result) { setNotice('已取消打开工程'); return; }
      projectRef.current = result;
      setProject(result);
      editing.reset(result.sessionId);
      updateDrafts({});
      setActivePath(null);
      setSelectedPath(null);
      setRecent([{ path: result.root, name: result.name }]);
      setNotice(`已打开 ${result.name}`);
      await editing.refresh();
    } catch (error) {
      const uncertain = error instanceof DesktopError && ['BRIDGE_TIMEOUT', 'BRIDGE_FAILURE', 'INVALID_RESPONSE', 'REQUEST_PENDING', 'REQUEST_UNKNOWN'].includes(error.code);
      if (!uncertain) unresolvedOpen.current = null;
      setNeedsRecovery(uncertain);
      setFailure(message(error));
      setNotice(uncertain ? '打开结果尚未确认，请查询原操作结果' : '打开失败，当前工程保持不变');
    }
    finally { openingProject.current = false; setBusy(false); }
  }

  async function openNode(node: TreeNode) {
    if (openingProject.current || unresolvedOpen.current || editor.busy || editor.uncertain || intentRef.current || !node.path || !projectRef.current) return;
    setSelectedPath(node.path);
    const selected = ++selection.current;
    if (node.kind !== 'content') { setNotice(`贴图：${node.path}`); return; }
    const path = node.path;
    if (documents.some(document => document.path === path)) { setActivePath(path); return; }
    const sessionId = projectRef.current.sessionId;
    const key = `${sessionId}:${path}`;
    if (pendingReads.current.has(key)) return;
    pendingReads.current.add(key);
    const currentGeneration = generation.current;
    setFailure('');
    setNotice(`正在读取 ${path}`);
    try {
      const document = await desktop.request<DocumentSnapshot>('read_document', {
        path, expectedRevision: editing.getSnapshot().state?.revision ?? 0,
      }, sessionId);
      if (currentGeneration !== generation.current || projectRef.current?.sessionId !== document.sessionId) return;
      await editing.refresh();
      if (currentGeneration !== generation.current) return;
      if (selection.current === selected) { setActivePath(path); setSelectedPath(path); }
      setNotice(`已读取 ${path}`);
    } catch (error) {
      if (currentGeneration === generation.current) { setFailure(`${path}：${message(error)}`); setNotice('内容读取失败'); }
    } finally { pendingReads.current.delete(key); }
  }

  function closeDocument(path: string) {
    void requestIntent({ kind: 'documents', paths: [path] });
  }

  const metadata = startup.phase === 'ready' ? startup.data.metadata : null;
  const status = startup.phase === 'ready' ? '离线元数据已就绪' : startup.phase === 'error' ? '启动未完成' : '正在连接桌面程序';

  return <div className={styles.app} data-startup={startup.phase}>
    <header className={styles.menu}>
      <span className={styles.brand}><span className={styles.mark}>M</span> MoMA</span>
      <span className={styles.caption}>模组助手</span>
    </header>
    <div className={styles.toolbar}>
      <button className={styles.button} disabled={!metadata || busy || editor.busy || editor.uncertain}
        onClick={() => needsRecovery ? void openProject() : void requestIntent({ kind: 'project' })}>{needsRecovery ? '查询打开结果' : '打开工程'}</button>
      <button className={styles.button} disabled={!documents.length || busy || editor.uncertain || decisionBusy}
        onClick={() => void editAction('save_opened')}>保存已打开内容</button>
      <button className={styles.button} disabled={!editor.state?.history.canUndo || busy || editor.busy || editor.uncertain}
        title={editor.state?.history.undoDescription || '没有可撤销的操作'} onClick={() => void editAction('undo')}>撤销</button>
      <button className={styles.button} disabled={!editor.state?.history.canRedo || busy || editor.busy || editor.uncertain}
        title={editor.state?.history.redoDescription || '没有可重做的操作'} onClick={() => void editAction('redo')}>重做</button>
      {editor.uncertain && <button className={styles.button} disabled={editor.busy} onClick={() => {
        void editing.recover().then(() => { setFailure(''); setNotice('已取得原操作结果'); }).catch(error => setFailure(message(error)));
      }}>查询操作结果</button>}
      <span title={project?.root}>{project?.name ?? '未打开工程'}</span>
    </div>
    <main className={styles.workbench}>
      <aside className={styles.sidebar} aria-label="文件">
        <h2 className={styles.panelHead}>文件</h2>
        {project ? <ProjectTree key={project.sessionId} nodes={project.tree} selectedPath={selectedPath} onOpen={node => void openNode(node)} /> : <p className={styles.emptySide}>尚未打开工程</p>}
      </aside>
      <section className={styles.editor} aria-label="编辑区">
        <div className={styles.tabBar} role="tablist" aria-label="打开的内容">
          {documents.length === 0 ? <div className={styles.tab}>欢迎</div> : documents.map(document => <div className={styles.documentTab} key={document.path} data-active={activePath === document.path}>
            <button role="tab" aria-selected={activePath === document.path} title={document.path} onClick={() => { selection.current += 1; setActivePath(document.path); setSelectedPath(document.path); }}>{document.name}{(document.dirty || document.path in drafts) && <span className={styles.dirty} aria-label="未保存">●</span>}</button>
            <button className={styles.closeTab} aria-label={`关闭 ${document.path}`} title="关闭" onClick={() => closeDocument(document.path)}>×</button>
          </div>)}
        </div>
        {failure && <div className={styles.problem} role="alert">{failure}<button aria-label="关闭提示" onClick={() => setFailure('')}>×</button></div>}
        {documents.length > 0 && <div className={styles.documentTools}>
          <span title={activePath ?? ''}>{activePath}</span>
          <button className={styles.button} disabled={documents.length < 2 && pendingReads.current.size === 0} onClick={() => {
            generation.current += 1;
            void editing.refresh().then(state => requestIntent({ kind: 'documents', paths: state.documents.filter(document => document.path !== activePath).map(document => document.path) })).catch(error => setFailure(message(error)));
          }}>关闭其他</button>
          <button className={styles.button} onClick={() => {
            generation.current += 1;
            void editing.refresh().then(state => requestIntent({ kind: 'documents', paths: state.documents.map(document => document.path) })).catch(error => setFailure(message(error)));
          }}>关闭全部</button>
        </div>}
        {documents.map(document => <section className={styles.document} key={document.path} hidden={activePath !== document.path} role="tabpanel" aria-label={document.path}>
          <h1>{document.name}</h1><p className={styles.description}>内容类型：{document.contentType}</p>
          <dl className={styles.fields}>{Object.entries(document.data).map(([key, value]) => <Fragment key={key}>
            <dt title={document.fieldDocs[key] ?? key}>{document.fieldNames[key] ?? key}</dt>
            <dd>{key === 'health' && document.category === 'units' ? <div className={styles.numberField} data-field-type="num">
              <input aria-label={document.fieldNames[key] ?? key} title={document.fieldDocs[key] ?? key}
                inputMode="decimal" value={drafts[document.path] ?? String(value)}
                disabled={busy || editor.uncertain || decisionBusy}
                aria-invalid={document.path in drafts && (!drafts[document.path].trim() || !Number.isFinite(Number(drafts[document.path])) || Number(drafts[document.path]) < 0)}
                onChange={event => updateDrafts({ ...draftsRef.current, [document.path]: event.target.value })}
                onBlur={() => { void flushDrafts().catch(error => setFailure(message(error))); }}
                onKeyDown={event => {
                  if (event.key === 'Enter') { event.preventDefault(); void flushDrafts().catch(error => setFailure(message(error))); }
                  if (event.key === 'Escape') { const next = { ...draftsRef.current }; delete next[document.path]; updateDrafts(next); setFailure(''); }
                }} />
            </div> : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}</dd>
          </Fragment>)}</dl>
        </section>)}
        {documents.length === 0 && <div className={styles.welcome}>
          <h1>模组工作台</h1>
          <p className={styles.description}>编辑内容，调整贴图，查看预览。</p>
          {project && <p>从左侧文件树选择内容，查看真实资料。</p>}
          {metadata && recent.length > 0 && <div className={styles.recent}><h2 className={styles.sectionTitle}>最近工程</h2>{recent.map(item => <button className={styles.recentProject} key={item.path} title={item.path} disabled={busy || needsRecovery || editor.busy || editor.uncertain} onClick={() => void requestIntent({ kind: 'project', path: item.path })}>{item.name}<span>{item.path}</span></button>)}</div>}
          {startup.phase === 'loading' && <p role="status">正在读取离线资料…</p>}
          {startup.phase === 'error' && <div role="alert"><p className={styles.error}>{startup.message}</p><button className={styles.button} onClick={load}>重新连接</button></div>}
          {metadata && <>
            <h2 className={styles.sectionTitle}>已加载的游戏资料</h2>
            <dl className={styles.catalogue}>
              <dt>游戏版本</dt><dd>{metadata.gameVersion}</dd>
              <dt>内容类型</dt><dd>{metadata.classCount}</dd>
              {metadata.categories.map(category => <Fragment key={category.name}>
                <dt>{categoryLabels[category.name] ?? '其他资料'}</dt><dd>{category.count}</dd>
              </Fragment>)}
            </dl>
          </>}
        </div>}
      </section>
      <aside className={styles.right} aria-label="预览与图层">
        <PreviewPanel document={documents.find(document => document.path === activePath)} />
        <h2 className={styles.panelHead}>图层</h2>
        <p className={styles.emptySide}>暂无图层</p>
      </aside>
    </main>
    <footer className={styles.status}><span role="status">{notice || status}</span><span>{metadata ? `游戏版本 ${metadata.gameVersion}` : '离线工作台'}</span></footer>
    {intent && <CloseDecision title={intent.kind === 'window' ? '关闭工作台' : intent.kind === 'project' ? '切换工程' : '关闭内容'}
      paths={documents.filter(document => (document.dirty || document.path in drafts) &&
        (intent.kind !== 'documents' || intent.paths.includes(document.path))).map(document => document.path)}
      busy={decisionBusy || editor.busy} error={decisionError} onChoose={choice => void executeIntent(intent, choice)} />}
  </div>;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请稍后重试。';
}
