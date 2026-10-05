import { useEffect, useId, useRef, useState, useSyncExternalStore } from 'react';
import { createResourceController } from './controller';
import type { SpriteAction, SpriteActionPayload, SpriteTargets } from './types';
import styles from './SpriteResources.module.css';

export type { SpriteAction, SpriteActionPayload, SpriteTarget, SpriteTargets } from './types';
export interface SpriteResourcesProps {
  sessionId: string;
  path: string;
  revision: number;
  load: () => Promise<SpriteTargets>;
  onAction: (action: SpriteAction, payload: SpriteActionPayload) => Promise<void>;
}

export function SpriteResources({ sessionId, path, revision, load, onAction }: SpriteResourcesProps) {
  const titleId = useId();
  const loadRef = useRef(load), actionRef = useRef(onAction);
  loadRef.current = load; actionRef.current = onAction;
  const [controller] = useState(() => createResourceController(() => loadRef.current(), (action, payload) => actionRef.current(action, payload)));
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot);
  const identity = JSON.stringify([sessionId, path, revision]);
  const current = state.identity === identity;
  const busy = !current || state.loading || state.pending !== null;
  const confirmation = current ? state.confirmation : null;
  const cancel = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const rowButtons = useRef(new Map<string, HTMLButtonElement>());
  const restoreFocus = useRef<{ owner: string; suffix: string; element: HTMLElement | null } | null>(null);
  const owner = JSON.stringify([sessionId, path]);

  useEffect(() => {
    void controller.start(identity);
    return () => controller.stop();
  }, [controller, identity]);

  useEffect(() => {
    if (!confirmation) return;
    cancel.current?.focus({ preventScroll: true });
  }, [confirmation]);

  useEffect(() => {
    const restore = restoreFocus.current;
    if (!restore || busy || confirmation || !current) return;
    restoreFocus.current = null;
    if (restore.owner !== owner) return;
    const previous = restore.element;
    if (previous?.isConnected && !previous.matches(':disabled')) previous.focus({ preventScroll: true });
    else rowButtons.current.get(restore.suffix)?.focus({ preventScroll: true });
  }, [busy, confirmation, current, owner]);

  function request(action: SpriteAction, suffix: string) {
    if (busy) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    void controller.request(action, suffix);
  }

  function cancelConfirmation() {
    if (busy || !confirmation) return;
    restoreFocus.current = { owner, suffix: confirmation.target.suffix, element: previousFocus.current };
    controller.cancelConfirmation();
  }

  async function confirm() {
    if (!confirmation) return;
    // Restore after React has enabled or replaced the row's action buttons.
    restoreFocus.current = { owner, suffix: confirmation.target.suffix, element: previousFocus.current };
    await controller.confirm();
  }

  return <section className={styles.resources} aria-labelledby={titleId} aria-busy={busy}>
    <header className={styles.heading}><h2 id={titleId}>贴图资源</h2>
      <button type="button" disabled={busy || Boolean(confirmation)} onClick={() => void controller.refresh()}>刷新资源</button>
    </header>
    {current && state.error && <p className={styles.error} role="alert">{state.error}</p>}
    {!current || state.loading ? <p className={styles.status} role="status">正在读取贴图资源…</p> : null}
    {current && !state.loading && !state.targets.length && !state.error && <p className={styles.status}>当前内容没有可操作的贴图类型。</p>}
    {current && state.targets.length > 0 && <ul className={styles.list} aria-label="贴图文件">
      {state.targets.map(target => <li key={target.suffix} className={styles.row} data-sprite-suffix={target.suffix}>
        <div className={styles.description}>
          <span className={styles.label}>{target.label}</span>
          <span className={styles.filename} title={target.path}>{target.path.split(/[\\/]/).at(-1) || target.path}</span>
          {!target.exists && <span className={styles.missing}>尚未导入</span>}
        </div>
        <div className={styles.actions}>
          <button ref={element => { if (element) rowButtons.current.set(target.suffix, element); else rowButtons.current.delete(target.suffix); }}
            type="button" disabled={busy || Boolean(confirmation)} aria-label={`${target.exists ? '替换' : '导入'}${target.label}贴图`}
            onClick={() => request('import_sprite', target.suffix)}>{target.exists ? '替换' : '导入'}</button>
          {target.exists && <>
            <button type="button" disabled={busy || Boolean(confirmation)} aria-label={`定位${target.label}贴图`}
              onClick={() => request('reveal_sprite', target.suffix)}>定位</button>
            <button type="button" disabled={busy || Boolean(confirmation)} aria-label={`删除${target.label}贴图`}
              onClick={() => request('delete_sprite', target.suffix)}>删除</button>
          </>}
        </div>
        {confirmation?.target.suffix === target.suffix && <div className={styles.confirmation} role="group"
          aria-label={`确认${confirmation.action === 'import_sprite' ? '替换' : '删除'}${target.label}贴图`}
          onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); cancelConfirmation(); } }}>
          <p>{confirmation.action === 'import_sprite' ? `选择新 PNG 后将替换“${target.label}”贴图。取消选文件会保留原图。`
            : `确定删除“${target.label}”贴图？可在当前会话中撤销。`}</p>
          <div className={styles.confirmActions}>
            <button type="button" disabled={busy} onClick={() => void confirm()}>{confirmation.action === 'import_sprite' ? '选择并替换' : '确认删除'}</button>
            <button ref={cancel} type="button" disabled={busy} onClick={cancelConfirmation}>取消</button>
          </div>
        </div>}
      </li>)}
    </ul>}
    {current && state.pending && <p className={styles.status} role="status">
      {state.pending.action === 'import_sprite' ? '等待文件选择或贴图写入…' : state.pending.action === 'delete_sprite' ? '正在删除贴图…' : '正在定位贴图…'}
    </p>}
  </section>;
}
