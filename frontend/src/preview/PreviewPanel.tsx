import { useCallback, useEffect, useRef, useState } from 'react';
import { desktop } from '../bridge/desktop';
import type { DocumentSnapshot } from '../workspace/types';
import { PreviewCanvas, type CanvasViewState } from './PreviewCanvas';
import { LAYOUT, Separator } from '../layout';
import type { PreviewResource, PreviewScene } from './types';
import styles from './PreviewPanel.module.css';
import { LayerTree, reconcileLayerView, revealLayerView, type LayerTreeProps, type LayerViewState } from '../layers/LayerTree';

type LayerBindings = Pick<LayerTreeProps, 'disabled' | 'drafts' | 'errors' | 'onDraft' | 'onCommit' | 'onReset' | 'onComposition' | 'onRevealParameters'>;
const emptyView: LayerViewState = { selectedId: null, hiddenIds: [], closedIds: [] };

export function resolvePreviewSplit(parentHeight: number, ratio: number | null) {
  const parent = Number.isFinite(parentHeight) ? Math.max(0, parentHeight) : 0;
  const height = Math.max(342, Math.min(620, parent * .65, parent - 160));
  const available = height - LAYOUT.separator;
  const enabled = available >= 230 + 190;
  const min = enabled ? 230 : Math.min(201, available);
  const max = enabled ? available - 190 : min;
  const wanted = ratio !== null && Number.isFinite(ratio) && ratio > 0 && ratio < 1 ? ratio : .55;
  const preview = Math.min(max, Math.max(min, available * wanted));
  return { height, available, preview, layers: available - preview, min, max, enabled };
}

export function PreviewPanel({ document, resourceRevision = 0, layers, openPaths = [], revealLayer, projectSessionId,
  previewRatio = null, onPreviewRatioChange, spriteZoom = 4 }: {
  document: DocumentSnapshot | undefined; resourceRevision?: number; layers?: LayerBindings; openPaths?: string[];
  revealLayer?: { path: string; nodeId: string; token: number };
  projectSessionId?: string | null;
  previewRatio?: number | null;
  onPreviewRatioChange?: (ratio: number | null) => void;
  spriteZoom?: number;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [parentHeight, setParentHeight] = useState(0);
  useEffect(() => {
    const parent = panelRef.current?.parentElement;
    if (!parent) return;
    let active = true;
    const measure = () => { if (active) setParentHeight(parent.clientHeight); };
    const observer = new ResizeObserver(measure);
    observer.observe(parent); measure();
    return () => { active = false; observer.disconnect(); };
  }, []);
  const split = resolvePreviewSplit(parentHeight, previewRatio);
  const session = document?.sessionId ?? null;
  const path = document?.path ?? null;
  // Unrelated saves and tab bookkeeping must not reset the user's viewport.
  const valid = document?.validData !== false;
  const dataIdentity = document?.sourceText ?? JSON.stringify(document?.data ?? null);
  const scope = `${session}:${path}`;
  const identity = `${scope}:${dataIdentity}:${resourceRevision}:${document?.revision}`;
  const [result, setResult] = useState<{ identity: string; scene: PreviewScene } | null>(null);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);
  const [views, setViews] = useState<Record<string, LayerViewState>>({});
  const canvasViews = useRef(new Map<string, CanvasViewState>());
  const saveCanvasView = useCallback((value: CanvasViewState) => { if (session && path) canvasViews.current.set(scope, value); }, [scope]);
  const revealed = useRef<number | undefined>(undefined);
  const view = views[scope] ?? emptyView;
  const live = result?.identity === identity;
  const scene = valid && result?.scene.sessionId === session && result.scene.path === path ? result.scene : null;
  const pathsKey = JSON.stringify(openPaths);
  const viewSession = projectSessionId ?? session;
  useEffect(() => {
    const keep = new Set(openPaths.map(item => `${viewSession}:${item}`));
    setViews(previous => Object.fromEntries(Object.entries(previous).filter(([key]) => keep.has(key))));
    for (const key of canvasViews.current.keys()) if (!keep.has(key)) canvasViews.current.delete(key);
  }, [viewSession, pathsKey]);
  useEffect(() => {
    if (!live || !scene?.tree) return;
    setViews(previous => ({ ...previous, [scope]: reconcileLayerView(scene.tree!, previous[scope] ?? emptyView) }));
  }, [live, scene, scope]);
  useEffect(() => {
    if (!live || !scene?.tree || revealLayer?.path !== path || revealed.current === revealLayer.token) return;
    revealed.current = revealLayer.token;
    setViews(previous => ({ ...previous, [scope]: revealLayerView(scene.tree!, previous[scope] ?? emptyView, revealLayer.nodeId) }));
  }, [revealLayer?.token, live, scene, scope]);
  const changeView = (change: (current: LayerViewState) => LayerViewState) => setViews(previous => ({ ...previous, [scope]: change(previous[scope] ?? emptyView) }));
  useEffect(() => {
    let current = true;
    setError('');
    if (!session || !path || !valid) { setResult(null); setLoading(false); return; }
    setLoading(true);
    void desktop.request<PreviewScene>('preview_scene', { path }, session)
      .then(scene => { if (current && scene.sessionId === session && scene.path === path && scene.revision === document?.revision) setResult({ identity, scene }); })
      .catch((failure: unknown) => { if (current) setError(failure instanceof Error ? failure.message : '预览读取失败。'); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [session, path, identity, refresh, valid]);
  const loadResource = useCallback((resourceId: string) => desktop.request<PreviewResource>(
    'preview_resource', { resourceId }, session), [session]);
  return <div ref={panelRef} className={styles.panel} data-preview-panel="true" style={{ height: split.height }}>
    <div className={styles.upper} style={{ height: split.preview }}>
    <div className={styles.heading}><h2>预览</h2>
      <button disabled={!document || !valid || loading} onClick={() => setRefresh(value => value + 1)}>{loading ? '读取中' : '刷新预览'}</button>
    </div>
    {error && <p className={styles.error} role="alert">{error}</p>}
    {!valid && <p className={styles.error}>源码尚未解析，无法预览。</p>}
    <div className={styles.canvasArea}>
      <PreviewCanvas key={scope} scene={scene} loadResource={loadResource} hiddenIds={view.hiddenIds} selectedId={view.selectedId}
        dynamicReady={live && !loading} spriteZoom={spriteZoom} initialView={canvasViews.current.get(scope)} onViewChange={saveCanvasView} />
    </div>
    </div>
    <Separator orientation="horizontal" label="预览与图层高度" value={split.preview} min={split.min} max={split.max}
      disabled={!split.enabled || !onPreviewRatioChange}
      onChange={pixels => onPreviewRatioChange?.(pixels / split.available)} onReset={() => onPreviewRatioChange?.(null)} />
    <div className={styles.lower} style={{ height: split.layers }}>
    <div className={styles.heading}><h2>图层</h2>{loading && <span role="status">正在同步</span>}</div>
    {document && scene?.tree && layers ? <LayerTree {...layers} sessionId={document.sessionId} path={document.path}
      nodes={scene.tree} selectedId={view.selectedId} hiddenIds={view.hiddenIds} closedIds={view.closedIds}
      revealToken={revealLayer?.path === path ? revealLayer.token : undefined}
      fieldNames={document.fieldNames} fieldDocs={document.fieldDocs} disabled={layers.disabled || !live || loading}
      onSelect={selectedId => changeView(current => ({ ...current, selectedId }))}
      onVisibility={(id, visible) => changeView(current => ({ ...current, hiddenIds: visible ? current.hiddenIds.filter(value => value !== id) : [...current.hiddenIds, id] }))}
      onExpanded={(id, expanded) => changeView(current => ({ ...current, closedIds: expanded ? current.closedIds.filter(value => value !== id) : [...current.closedIds, id] }))} />
      : <p className={styles.empty}>当前内容没有可用图层。</p>}
    </div>
  </div>;
}
