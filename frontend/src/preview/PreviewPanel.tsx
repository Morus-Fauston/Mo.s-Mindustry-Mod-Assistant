import { useCallback, useEffect, useState } from 'react';
import { desktop } from '../bridge/desktop';
import type { DocumentSnapshot } from '../workspace/types';
import { PreviewCanvas } from './PreviewCanvas';
import type { PreviewResource, PreviewScene } from './types';
import styles from './PreviewPanel.module.css';

export function PreviewPanel({ document, resourceRevision = 0 }: { document: DocumentSnapshot | undefined; resourceRevision?: number }) {
  const session = document?.sessionId ?? null;
  const path = document?.path ?? null;
  // Unrelated saves and tab bookkeeping must not reset the user's viewport.
  const valid = document?.validData !== false;
  const dataIdentity = document?.sourceText ?? JSON.stringify(document?.data ?? null);
  const identity = `${session}:${path}:${dataIdentity}:${resourceRevision}`;
  const [result, setResult] = useState<{ identity: string; scene: PreviewScene } | null>(null);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let current = true;
    setError('');
    setResult(null);
    if (!session || !path || !valid) { setLoading(false); return; }
    setLoading(true);
    void desktop.request<PreviewScene>('preview_scene', { path }, session)
      .then(scene => { if (current && scene.sessionId === session) setResult({ identity, scene }); })
      .catch((failure: unknown) => { if (current) setError(failure instanceof Error ? failure.message : '预览读取失败。'); })
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [session, path, identity, refresh, valid]);
  const loadResource = useCallback((resourceId: string) => desktop.request<PreviewResource>(
    'preview_resource', { resourceId }, session), [session]);
  return <>
    <div className={styles.heading}><h2>预览</h2>
      <button disabled={!document || !valid || loading} onClick={() => setRefresh(value => value + 1)}>{loading ? '读取中' : '刷新预览'}</button>
    </div>
    {error && <p className={styles.error} role="alert">{error}</p>}
    {!valid && <p className={styles.error}>源码尚未解析，无法预览。</p>}
    <PreviewCanvas key={`${session}:${path}`} scene={result?.identity === identity ? result.scene : null} loadResource={loadResource} />
  </>;
}
