import { Fragment, useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { desktop, DesktopError, type BootstrapData } from './bridge/desktop';
import { ProjectTree } from './workspace/ProjectTree';
import type { DocumentSnapshot, ProjectSnapshot, RecentProject, TreeNode } from './workspace/types';
import styles from './App.module.css';
import { createEditingClient } from './editing/client';
import { CloseDecision, type CloseChoice } from './editing/CloseDecision';
import { PreviewPanel } from './preview/PreviewPanel';
import { NestedForm, decodeFieldKey, encodeFieldKey, type NestedFormPlan, type ObjectPath } from './nested/NestedForm';
import { createDraftStore } from './editing/drafts';
import type { ReferenceResult } from './references/types';
import { SpriteResources, type SpriteTargets } from './resources/SpriteResources';
import { ResourceField, isResourceField, findResourceField } from './resource_fields/ResourceField';
import { WeaponArray, isWeaponArrayField, findWeaponField } from './weapons/WeaponArray';
import { ResearchField, isResearchField, findResearchField } from './research/ResearchField';
import { SourceEditor, SOURCE_DRAFT_FIELD } from './source/SourceEditor';

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
  const [draftStore] = useState(() => createDraftStore(async (path, field, text) => {
    if (field === SOURCE_DRAFT_FIELD) { await editing.run('set_source', { path, text }); return; }
    const current = editing.getSnapshot().state?.documents.find(document => document.path === path);
    const resource = current?.form && findResourceField(current.form as NestedFormPlan, field);
    const research = current?.form && findResearchField(current.form as NestedFormPlan, field);
    await editing.run(research ? 'research_set' : resource ? 'resource_set' : 'set_field', { path, ...decodeFieldKey(field), text });
  }));
  const draftState = useSyncExternalStore(draftStore.subscribe, draftStore.getSnapshot);
  const drafts = draftState.drafts;
  const [intent, setIntent] = useState<CloseIntent | null>(null);
  const intentRef = useRef<CloseIntent | null>(null);
  const [decisionBusy, setDecisionBusy] = useState(false);
  const [decisionError, setDecisionError] = useState('');
  const [activePath, setActivePath] = useState<string | null>(null);
  const [sourceViews, setSourceViews] = useState<Record<string, { mode: 'form' | 'source'; seen: boolean }>>({});
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [recent, setRecent] = useState<RecentProject[]>([]);
  const [busy, setBusy] = useState(false);
  const openingProject = useRef(false);
  const unresolvedOpen = useRef<Opening | null>(null);
  const [needsRecovery, setNeedsRecovery] = useState(false);
  const [notice, setNotice] = useState('');
  const [failure, setFailure] = useState('');
  const [resourceRevision, setResourceRevision] = useState(0);
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

  useEffect(() => {
    const session = project?.sessionId;
    if (!session) { setResourceRevision(0); return; }
    let alive = true, pending = false;
    async function refreshResources() {
      if (pending || editing.getSnapshot().busy || openingProject.current || intentRef.current) return;
      pending = true;
      try {
        const result = await desktop.request<{ sessionId: string; resourceRevision: number; tree: TreeNode[] }>(
          'resource_state', {}, session!);
        if (alive && projectRef.current?.sessionId === result.sessionId) {
          setResourceRevision(result.resourceRevision);
          setProject(current => current?.sessionId === result.sessionId ? { ...current, tree: result.tree } : current);
        }
      } catch (error) { if (alive) setFailure(message(error)); }
      finally { pending = false; }
    }
    void refreshResources();
    const timer = setInterval(() => void refreshResources(), 2000);
    return () => { alive = false; clearInterval(timer); };
  }, [project?.sessionId, editor.state?.revision, editing]);

  const flushDrafts = draftStore.flush;

  async function commitDraft(path: string, field: string) {
    try { await draftStore.commit(path, field); setFailure(''); }
    catch (error) { setFailure(message(error)); throw error; }
  }

  async function switchView(path: string, mode: 'form' | 'source') {
    if (draftStore.getSnapshot().composing) { setFailure('请结束中文输入后再切换视图。'); return; }
    const session = projectRef.current?.sessionId;
    const fields = draftStore.getSnapshot().drafts[path] ?? {};
    try {
      for (const field of Object.keys(fields)) await commitDraft(path, field);
    } catch {
      // Invalid source remains visible as a draft; the old form is explicitly read-only.
      if (mode === 'source' || !(SOURCE_DRAFT_FIELD in fields)) return;
    }
    if (session === projectRef.current?.sessionId) setSourceViews(previous => ({ ...previous, [path]: { mode, seen: true } }));
  }

  async function formatSource(document: DocumentSnapshot) {
    const owner = generation.current;
    const path = document.path, text = draftStore.getSnapshot().drafts[path]?.[SOURCE_DRAFT_FIELD] ?? document.sourceText ?? '';
    try {
      const result = await desktop.request<{ text: string }>('format_source', {
        path, text, expectedRevision: editing.getSnapshot().state?.revision,
      }, document.sessionId);
      const currentDocument = editing.getSnapshot().state?.documents.find(item => item.path === path);
      if (owner !== generation.current || projectRef.current?.sessionId !== document.sessionId ||
          !currentDocument ||
          (draftStore.getSnapshot().drafts[path]?.[SOURCE_DRAFT_FIELD] ?? currentDocument.sourceText ?? '') !== text) return;
      draftStore.set(path, SOURCE_DRAFT_FIELD, result.text);
      await commitDraft(path, SOURCE_DRAFT_FIELD);
    } catch (error) {
      if (owner !== generation.current || projectRef.current?.sessionId !== document.sessionId) return;
      setFailure(message(error)); throw error;
    }
  }

  async function formAction(path: string, action: string, payload: Record<string, unknown>) {
    try {
      setFailure('');
      const session = projectRef.current?.sessionId;
      const target = typeof payload.field === 'string' && ['set_field', 'resource_set', 'research_set', 'delete_field'].includes(action)
        ? { path, field: encodeFieldKey((payload.objectPath ?? []) as ObjectPath, payload.field) } : undefined;
      const replacedDraft = target ? draftStore.getSnapshot().drafts[path]?.[target.field] : undefined;
      await draftStore.flush(target);
      if (session !== projectRef.current?.sessionId) return;
      await editing.run(action, { ...payload, path });
      if (target && draftStore.getSnapshot().drafts[path]?.[target.field] === replacedDraft) {
        draftStore.resetField(path, target.field);
      }
    } catch (error) { setFailure(message(error)); throw error; }
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
        draftStore.removePaths(target.paths);
        setSourceViews(previous => Object.fromEntries(Object.entries(previous).filter(([path]) => !target.paths.includes(path))));
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
    await draftStore.settled();
    if (editing.getSnapshot().busy) return;
    // Reconcile completed reads before closing, including responses still in flight.
    const state = await editing.refresh().catch(error => { setFailure(message(error)); return null; });
    if (!state) return;
    const dirty = state.documents.filter(document => document.dirty || document.path in draftStore.getSnapshot().drafts)
      .filter(document => target.kind !== 'documents' || target.paths.includes(document.path));
    if (dirty.length) { intentRef.current = target; setIntent(target); setDecisionError(''); }
    else await executeIntent(target, 'discard');
  }

  const handlers = useRef({ requestIntent, editAction });
  handlers.current = { requestIntent, editAction };
  useEffect(() => {
    const close = () => { void handlers.current.requestIntent({ kind: 'window' }); };
    const keys = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey || event.isComposing || intentRef.current) return;
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
      if (!snapshot.busy && !snapshot.uncertain && !intentRef.current && !draftStore.getSnapshot().composing &&
          (snapshot.state?.documents.some(document => document.dirty) || Object.keys(draftStore.getSnapshot().drafts).length)) {
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
      draftStore.reset();
      setSourceViews({});
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
      if (document.validData === false) setSourceViews(previous => ({ ...previous, [path]: { mode: 'source', seen: true } }));
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
          <div className={styles.viewTools} role="group" aria-label="编辑视图">
            <button type="button" aria-pressed={(sourceViews[document.path]?.mode ?? 'form') === 'form'}
              onClick={() => void switchView(document.path, 'form')}>表单</button>
            <button type="button" aria-pressed={sourceViews[document.path]?.mode === 'source'}
              onClick={() => void switchView(document.path, 'source')}>JSON 源码</button>
            {SOURCE_DRAFT_FIELD in (drafts[document.path] ?? {}) && <button type="button" disabled={draftState.composing || editor.busy}
              onClick={() => { draftStore.resetField(document.path, SOURCE_DRAFT_FIELD); setFailure(''); }}>放弃源码输入</button>}
          </div>
          <div hidden={sourceViews[document.path]?.mode === 'source'}>
          {SOURCE_DRAFT_FIELD in (drafts[document.path] ?? {}) && <p className={styles.sourceWarning} role="status">源码输入尚未应用，以下显示上一次有效内容，暂不可编辑。</p>}
          {document.validData === false ? <p className={styles.sourceWarning}>源码无法解析，尚无可用表单。请切换到 JSON 源码修复。</p> :
          <NestedForm document={document} plan={document.form as NestedFormPlan} drafts={drafts[document.path] ?? {}} errors={draftState.errors[document.path] ?? {}}
            renderSpecialField={(field, objectPath, props, renderForm) => isResourceField(field) ? <ResourceField {...props} field={field} objectPath={objectPath} />
              : isResearchField(field) ? <ResearchField {...props} field={field} objectPath={objectPath} />
              : isWeaponArrayField(field) ? <WeaponArray {...props} field={field} objectPath={objectPath} renderForm={renderForm} /> : undefined}
            disabled={busy || editor.uncertain || decisionBusy || SOURCE_DRAFT_FIELD in (drafts[document.path] ?? {})}
            onLoadReference={(field, query) => {
              const plan = document.form as NestedFormPlan;
              const weapon = findWeaponField(plan, field);
              const action = findResearchField(plan, field) ? 'research_reference_candidates' : findResourceField(plan, field) ? 'resource_reference_candidates'
                : weapon && (weapon.control === 'weapon_array' || weapon.control === 'reference' && weapon.name === 'name') ? 'weapon_reference_candidates' : 'reference_candidates';
              return desktop.request<ReferenceResult>(action, { path: document.path, ...decodeFieldKey(field), query }, document.sessionId);
            }}
            onDraft={(field, text) => draftStore.set(document.path, field, text)}
            onComposition={(field, active) => draftStore.composition(document.path, field, active)}
            onReset={field => { draftStore.resetField(document.path, field); setFailure(''); }}
            onCommit={field => commitDraft(document.path, field)}
            onAction={(action, payload) => formAction(document.path, action, payload)} />}
          </div>
          {(sourceViews[document.path]?.seen || document.validData === false) && <div hidden={sourceViews[document.path]?.mode !== 'source'}>
            <SourceEditor identity={JSON.stringify([document.sessionId, document.path])}
              text={drafts[document.path]?.[SOURCE_DRAFT_FIELD] ?? document.sourceText ?? ''}
              error={SOURCE_DRAFT_FIELD in (drafts[document.path] ?? {})
                ? draftState.errors[document.path]?.[SOURCE_DRAFT_FIELD] ?? '' : document.sourceError?.message ?? ''}
              disabled={busy || editor.uncertain || decisionBusy || activePath !== document.path || sourceViews[document.path]?.mode !== 'source'}
              onDraft={text => draftStore.set(document.path, SOURCE_DRAFT_FIELD, text)}
              onCommit={() => commitDraft(document.path, SOURCE_DRAFT_FIELD)}
              onComposition={active => draftStore.composition(document.path, SOURCE_DRAFT_FIELD, active)}
              onFormat={() => formatSource(document)} onAction={action => void editAction(action)} />
          </div>}
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
        <PreviewPanel document={documents.find(document => document.path === activePath)} resourceRevision={resourceRevision} />
        <h2 className={styles.panelHead}>图层</h2>
        <p className={styles.emptySide}>暂无图层</p>
        {project && activePath && documents.find(document => document.path === activePath)?.validData !== false && <SpriteResources key={`${project.sessionId}:${activePath}`}
          sessionId={project.sessionId} path={activePath} revision={(editor.state?.revision ?? 0) + resourceRevision}
          load={() => desktop.request<SpriteTargets>('sprite_targets', { path: activePath }, project.sessionId)}
          onAction={async (action, payload) => {
            await flushDrafts();
            if (projectRef.current?.sessionId !== project.sessionId) return;
            await editing.run(action, { ...payload, path: activePath });
          }} />}
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
