import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import type { PreviewResource, PreviewScene } from './types';
import { createDecodeBudget, decodePng, validateResource } from './resources';
import { canvasBackingSize, fitViewport, panBy, sceneBounds, screenToScene, zoomAt } from './viewport';
import type { Point, Size, Viewport } from './viewport';
import styles from './PreviewCanvas.module.css';

export interface PreviewCanvasProps {
  scene: PreviewScene | null;
  loadResource: (id: string) => Promise<PreviewResource>;
}

interface Images {
  scene: PreviewScene | null;
  images: Map<string, HTMLImageElement>;
  errors: string[];
  loading: boolean;
}

export function PreviewCanvas({ scene, loadResource }: PreviewCanvasProps) {
  const hasLayers = Boolean(scene && (scene.layers.length || scene.circles.length));
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const surfaceRef = useRef<HTMLDivElement>(null);
  const loaderRef = useRef(loadResource);
  loaderRef.current = loadResource;
  const [size, setSize] = useState<Size>({ width: 1, height: 1 });
  const [dpr, setDpr] = useState(() => window.devicePixelRatio || 1);
  const [themeVersion, setThemeVersion] = useState(0);
  const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, scale: 1 });
  const [checker, setChecker] = useState(true);
  const [grid, setGrid] = useState(false);
  const [retry, setRetry] = useState(0);
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ id: number; point: Point } | null>(null);
  const [loaded, setLoaded] = useState<Images>({ scene: null, images: new Map(), errors: [], loading: false });

  useLayoutEffect(() => {
    const surface = surfaceRef.current!;
    const measure = () => {
      const rect = surface.getBoundingClientRect();
      setSize(previous => previous.width === rect.width && previous.height === rect.height
        ? previous : { width: Math.max(1, rect.width), height: Math.max(1, rect.height) });
      setDpr(window.devicePixelRatio || 1);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(surface);
    window.addEventListener('resize', measure);
    measure();
    return () => { observer.disconnect(); window.removeEventListener('resize', measure); };
  }, []);

  useEffect(() => {
    const query = matchMedia(`(resolution: ${dpr}dppx)`);
    const change = () => setDpr(window.devicePixelRatio || 1);
    query.addEventListener('change', change);
    return () => query.removeEventListener('change', change);
  }, [dpr]);

  useEffect(() => {
    const observer = new MutationObserver(() => setThemeVersion(value => value + 1));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class', 'style'] });
    return () => observer.disconnect();
  }, []);

  useLayoutEffect(() => {
    setViewport(fitViewport(sceneBounds(scene), size));
    drag.current = null;
    setDragging(false);
  }, [scene, size]);

  useEffect(() => {
    const controller = new AbortController();
    const images = new Map<string, HTMLImageElement>();
    const errors: string[] = [];
    const loader = loaderRef.current;
    setLoaded({ scene, images, errors: [], loading: Boolean(scene?.layers.length) });
    if (!scene) return () => controller.abort();
    const ids = [...new Set(scene.layers.map(layer => layer.resourceId))];
    const reservePixels = createDecodeBudget(scene.layers);
    let next = 0;
    const worker = async () => {
      while (!controller.signal.aborted && next < ids.length) {
        const id = ids[next++];
        try {
          const resource = await loader(id);
          if (controller.signal.aborted) return;
          validateResource(resource, scene.sessionId, id);
          reservePixels(resource);
          const image = await decodePng(resource, controller.signal);
          if (controller.signal.aborted) { image.src = ''; return; }
          images.set(id, image);
        } catch (error: unknown) {
          if (controller.signal.aborted) return;
          const label = scene.layers.find(layer => layer.resourceId === id)?.tooltip;
          errors.push(`${label ? `${label}：` : ''}${error instanceof Error ? error.message : '贴图读取失败。'}`);
        }
      }
    };
    void Promise.all(Array.from({ length: Math.min(4, ids.length) }, worker)).then(() => {
      if (!controller.signal.aborted) setLoaded({ scene, images, errors, loading: false });
    });
    return () => {
      controller.abort();
      for (const image of images.values()) image.src = '';
      images.clear();
    };
  }, [scene, retry]);

  useLayoutEffect(() => {
    const canvas = canvasRef.current!;
    const backing = canvasBackingSize(size, dpr);
    canvas.width = backing.width; canvas.height = backing.height;
    const context = canvas.getContext('2d');
    if (!context) return;
    context.setTransform(backing.width / size.width, 0, 0, backing.height / size.height, 0, 0);
    context.imageSmoothingEnabled = false;
    const tokens = getComputedStyle(canvas);
    context.fillStyle = tokens.getPropertyValue('--preview');
    context.fillRect(0, 0, size.width, size.height);
    if (checker) {
      context.fillStyle = tokens.getPropertyValue('--preview-muted');
      context.globalAlpha = 0.11;
      for (let y = 0; y < size.height; y += 12) {
        for (let x = (y / 12 % 2) * 12; x < size.width; x += 24) context.fillRect(x, y, 12, 12);
      }
      context.globalAlpha = 1;
    }
    if (grid) {
      let step = viewport.scale * 4;
      while (step < 16) step *= 2;
      context.strokeStyle = tokens.getPropertyValue('--preview-muted');
      context.globalAlpha = 0.3;
      context.lineWidth = 1;
      context.beginPath();
      for (let x = ((viewport.x % step) + step) % step; x < size.width; x += step) { context.moveTo(x, 0); context.lineTo(x, size.height); }
      for (let y = ((viewport.y % step) + step) % step; y < size.height; y += step) { context.moveTo(0, y); context.lineTo(size.width, y); }
      context.stroke(); context.globalAlpha = 1;
    }
    if (!scene) return;
    context.translate(viewport.x, viewport.y); context.scale(viewport.scale, viewport.scale);
    const items = [
      ...scene.layers.map(layer => ({ kind: 'layer' as const, value: layer })),
      ...scene.circles.map(circle => ({ kind: 'circle' as const, value: circle })),
    ].sort((a, b) => a.value.z - b.value.z);
    for (const item of items) {
      if (item.kind === 'circle') {
        const circle = item.value;
        context.fillStyle = circle.color;
        context.beginPath(); context.arc(circle.cx, circle.cy, circle.radius, 0, Math.PI * 2); context.fill();
      } else {
        const layer = item.value;
        const image = loaded.scene === scene ? loaded.images.get(layer.resourceId) : null;
        if (!image) continue;
        context.save();
        context.translate(layer.x + (layer.flipX ? layer.width : 0), layer.y);
        if (layer.flipX) context.scale(-1, 1);
        context.drawImage(image, 0, 0, layer.width, layer.height);
        context.restore();
      }
    }
  }, [scene, loaded, viewport, size, dpr, checker, grid, themeVersion]);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const wheel = (event: WheelEvent) => {
      if (!hasLayers) return;
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? size.height : 1);
      const factor = Math.exp(-Math.max(-1000, Math.min(1000, delta)) * 0.0015);
      setViewport(current => zoomAt(current, { x: event.clientX - rect.left, y: event.clientY - rect.top }, factor));
    };
    canvas.addEventListener('wheel', wheel, { passive: false });
    return () => canvas.removeEventListener('wheel', wheel);
  }, [hasLayers, size.height]);

  const fit = () => setViewport(fitViewport(sceneBounds(scene), size));
  const zoom = (factor: number) => setViewport(current => zoomAt(current, { x: size.width / 2, y: size.height / 2 }, factor));
  const pointerDown = (event: PointerEvent<HTMLCanvasElement>) => {
    if (!hasLayers || (event.button !== 0 && event.button !== 1)) return;
    event.preventDefault(); event.currentTarget.focus();
    event.currentTarget.setPointerCapture(event.pointerId);
    drag.current = { id: event.pointerId, point: { x: event.clientX, y: event.clientY } };
    setDragging(true);
  };
  const pointerMove = (event: PointerEvent<HTMLCanvasElement>) => {
    const current = drag.current;
    if (current && current.id === event.pointerId) {
      setViewport(view => panBy(view, { x: event.clientX - current.point.x, y: event.clientY - current.point.y }));
      drag.current = { id: event.pointerId, point: { x: event.clientX, y: event.clientY } };
    } else if (scene) {
      const rect = event.currentTarget.getBoundingClientRect();
      const point = screenToScene(viewport, { x: event.clientX - rect.left, y: event.clientY - rect.top });
      const layer = [...scene.layers].sort((a, b) => b.z - a.z).find(item => point.x >= item.x && point.y >= item.y && point.x <= item.x + item.width && point.y <= item.y + item.height);
      event.currentTarget.title = layer?.tooltip || '滚轮缩放，拖动平移；方向键平移，加减键缩放，回车适应窗口。';
    }
  };
  const pointerEnd = (event: PointerEvent<HTMLCanvasElement>) => {
    if (drag.current?.id !== event.pointerId) return;
    drag.current = null; setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  const keyDown = (event: KeyboardEvent<HTMLCanvasElement>) => {
    if (!hasLayers) return;
    const moves: Record<string, Point> = { ArrowLeft: { x: -20, y: 0 }, ArrowRight: { x: 20, y: 0 }, ArrowUp: { x: 0, y: -20 }, ArrowDown: { x: 0, y: 20 } };
    if (moves[event.key]) { event.preventDefault(); setViewport(current => panBy(current, moves[event.key])); }
    else if (event.key === '+' || event.key === '=') { event.preventDefault(); zoom(1.25); }
    else if (event.key === '-') { event.preventDefault(); zoom(0.8); }
    else if (event.key === 'Enter' || event.key === 'Home') { event.preventDefault(); fit(); }
  };

  const ready = hasLayers;
  const current = loaded.scene === scene;
  const loading = Boolean(scene?.layers.length) && (!current || loaded.loading);
  const errors = current ? loaded.errors : [];
  const visibleLayers = current && (loaded.images.size > 0 || Boolean(scene?.circles.length));
  const emptyMessage = !scene ? '选择内容后显示贴图' : !hasLayers ? scene.status === 'missing' ? '未找到可用贴图' : '当前内容没有预览图层' : loading && !visibleLayers ? '正在读取贴图…' : '';
  const previewStatus = loading ? 'loading' : !hasLayers ? scene?.status || 'empty'
    : errors.length || scene?.warnings.length || scene?.status === 'missing' ? visibleLayers ? 'partial' : 'error' : 'ready';
  return <section className={styles.preview} aria-label="贴图预览" data-preview-status={previewStatus}>
    <div className={styles.toolbar} role="toolbar" aria-label="预览视口">
      <button className={styles.button} disabled={!ready} onClick={fit}>适应</button>
      <button className={styles.button} disabled={!ready} onClick={() => zoom(0.8)} aria-label="缩小预览">−</button>
      <span className={styles.zoom}>{Math.round(viewport.scale * 100)}%</span>
      <button className={styles.button} disabled={!ready} onClick={() => zoom(1.25)} aria-label="放大预览">＋</button>
      <button className={styles.button} aria-pressed={checker} onClick={() => setChecker(value => !value)}>棋盘</button>
      <button className={styles.button} aria-pressed={grid} onClick={() => setGrid(value => !value)}>网格</button>
    </div>
    <div ref={surfaceRef} className={styles.surface}>
      <canvas ref={canvasRef} className={styles.canvas} tabIndex={ready ? 0 : -1} aria-label="静态贴图预览；滚轮缩放，拖动平移，回车适应窗口" data-dragging={dragging}
        data-scale={viewport.scale} data-offset-x={viewport.x} data-offset-y={viewport.y} data-dpr={dpr}
        onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerEnd} onPointerCancel={pointerEnd} onLostPointerCapture={pointerEnd} onKeyDown={keyDown} onDoubleClick={fit}>
        当前浏览器无法显示贴图预览。
      </canvas>
      {emptyMessage && <div className={styles.message} role="status">{emptyMessage}</div>}
    </div>
    {(previewStatus === 'partial' || Boolean(scene?.warnings.length) || errors.length > 0) && <div className={styles.feedback}>
      {previewStatus === 'partial' && <p role="status">部分贴图不可用，已显示可用图层。</p>}
      {scene?.warnings.map((warning, index) => <p key={`warning-${index}`}>{warning}</p>)}
      {errors.map((error, index) => <p className={styles.error} key={`error-${index}`} role="alert">{error}</p>)}
      {errors.length > 0 && <button className={styles.button} onClick={() => setRetry(value => value + 1)}>重新载入贴图</button>}
    </div>}
  </section>;
}
