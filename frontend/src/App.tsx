import { Fragment, useCallback, useEffect, useRef, useState } from 'react';
import { desktop, DesktopError, type BootstrapData } from './bridge/desktop';
import { ProjectTree } from './workspace/ProjectTree';
import type { DocumentSnapshot, ProjectSnapshot, RecentProject, TreeNode } from './workspace/types';
import styles from './App.module.css';

type Startup = { phase: 'loading' } | { phase: 'ready'; data: BootstrapData } | { phase: 'error'; message: string };
type Opening = { action: string; payload: Record<string, unknown>; sessionId: string | null; requestId: string };

const categoryLabels: Record<string, string> = {
  Units: '单位', UnitTypes: '单位', Blocks: '方块', Weapons: '武器', Bullets: '子弹',
  Items: '物品', Liquids: '液体', StatusEffects: '状态效果',
  Planets: '星球', Sectors: '战区', SectorPresets: '战区',
};

export function App() {
  const [startup, setStartup] = useState<Startup>({ phase: 'loading' });
  const [project, setProject] = useState<ProjectSnapshot | null>(null);
  const projectRef = useRef<ProjectSnapshot | null>(null);
  const [documents, setDocuments] = useState<DocumentSnapshot[]>([]);
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

  async function openProject(path?: string) {
    if (openingProject.current) return;
    openingProject.current = true;
    setBusy(true);
    setFailure('');
    setNotice(path ? '正在打开工程…' : '请选择工程目录');
    generation.current += 1;
    const recovering = unresolvedOpen.current !== null;
    const operation: Opening = unresolvedOpen.current ?? {
      action: path ? 'open_project' : 'choose_project', payload: path ? { path } : {},
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
      setDocuments([]);
      setActivePath(null);
      setSelectedPath(null);
      setRecent([{ path: result.root, name: result.name }]);
      setNotice(`已打开 ${result.name}`);
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
    if (openingProject.current || unresolvedOpen.current || !node.path || !projectRef.current) return;
    setSelectedPath(node.path);
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
      const document = await desktop.request<DocumentSnapshot>('read_document', { path }, sessionId);
      if (currentGeneration !== generation.current || projectRef.current?.sessionId !== document.sessionId) return;
      setDocuments(current => current.some(item => item.path === path) ? current : [...current, document]);
      setActivePath(path);
      setSelectedPath(path);
      setNotice(`已读取 ${path}`);
    } catch (error) {
      if (currentGeneration === generation.current) { setFailure(`${path}：${message(error)}`); setNotice('内容读取失败'); }
    } finally { pendingReads.current.delete(key); }
  }

  function closeDocument(path: string) {
    const index = documents.findIndex(document => document.path === path);
    const remaining = documents.filter(document => document.path !== path);
    setDocuments(remaining);
    if (activePath === path) {
      const next = remaining[Math.min(index, remaining.length - 1)]?.path ?? null;
      setActivePath(next);
      setSelectedPath(next);
    }
  }

  const metadata = startup.phase === 'ready' ? startup.data.metadata : null;
  const status = startup.phase === 'ready' ? '离线元数据已就绪' : startup.phase === 'error' ? '启动未完成' : '正在连接桌面程序';

  return <div className={styles.app} data-startup={startup.phase}>
    <header className={styles.menu}>
      <span className={styles.brand}><span className={styles.mark}>M</span> MoMA</span>
      <span className={styles.caption}>模组助手</span>
    </header>
    <div className={styles.toolbar}><button className={styles.button} disabled={!metadata || busy} onClick={() => void openProject()}>{needsRecovery ? '查询打开结果' : '打开工程'}</button><span title={project?.root}>{project?.name ?? '未打开工程'}</span></div>
    <main className={styles.workbench}>
      <aside className={styles.sidebar} aria-label="文件">
        <h2 className={styles.panelHead}>文件</h2>
        {project ? <ProjectTree key={project.sessionId} nodes={project.tree} selectedPath={selectedPath} onOpen={node => void openNode(node)} /> : <p className={styles.emptySide}>尚未打开工程</p>}
      </aside>
      <section className={styles.editor} aria-label="编辑区">
        <div className={styles.tabBar} role="tablist" aria-label="打开的内容">
          {documents.length === 0 ? <div className={styles.tab}>欢迎</div> : documents.map(document => <div className={styles.documentTab} key={document.path} data-active={activePath === document.path}>
            <button role="tab" aria-selected={activePath === document.path} title={document.path} onClick={() => { setActivePath(document.path); setSelectedPath(document.path); }}>{document.name}</button>
            <button className={styles.closeTab} aria-label={`关闭 ${document.path}`} title="关闭" onClick={() => closeDocument(document.path)}>×</button>
          </div>)}
        </div>
        {failure && <div className={styles.problem} role="alert">{failure}<button aria-label="关闭提示" onClick={() => setFailure('')}>×</button></div>}
        {documents.length > 0 && <div className={styles.documentTools}>
          <span title={activePath ?? ''}>{activePath}</span>
          <button className={styles.button} disabled={documents.length < 2 && pendingReads.current.size === 0} onClick={() => { generation.current += 1; setDocuments(current => current.filter(document => document.path === activePath)); }}>关闭其他</button>
          <button className={styles.button} onClick={() => { generation.current += 1; setDocuments([]); setActivePath(null); setSelectedPath(null); }}>关闭全部</button>
        </div>}
        {documents.map(document => <section className={styles.document} key={document.path} hidden={activePath !== document.path} role="tabpanel" aria-label={document.path}>
          <h1>{document.name}</h1><p className={styles.description}>内容类型：{document.contentType}</p>
          <dl className={styles.fields}>{Object.entries(document.data).map(([key, value]) => <Fragment key={key}>
            <dt title={document.fieldDocs[key] ?? key}>{document.fieldNames[key] ?? key}</dt>
            <dd>{typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}</dd>
          </Fragment>)}</dl>
        </section>)}
        {documents.length === 0 && <div className={styles.welcome}>
          <h1>模组工作台</h1>
          <p className={styles.description}>编辑内容，调整贴图，查看预览。</p>
          {project && <p>从左侧文件树选择内容，查看真实资料。</p>}
          {metadata && recent.length > 0 && <div className={styles.recent}><h2 className={styles.sectionTitle}>最近工程</h2>{recent.map(item => <button className={styles.recentProject} key={item.path} title={item.path} disabled={busy || needsRecovery} onClick={() => void openProject(item.path)}>{item.name}<span>{item.path}</span></button>)}</div>}
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
        <h2 className={styles.panelHead}>预览</h2>
        <div className={styles.preview}>选择内容后显示贴图</div>
        <h2 className={styles.panelHead}>图层</h2>
        <p className={styles.emptySide}>暂无图层</p>
      </aside>
    </main>
    <footer className={styles.status}><span role="status">{notice || status}</span><span>{metadata ? `游戏版本 ${metadata.gameVersion}` : '离线工作台'}</span></footer>
  </div>;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请稍后重试。';
}
