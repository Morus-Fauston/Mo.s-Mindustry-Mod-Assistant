import { useEffect, useRef } from 'react';
import styles from './CloseDecision.module.css';

export type CloseChoice = 'save' | 'discard' | 'cancel';

export function CloseDecision({ title, paths, busy, error, onChoose, recovery }: {
  title: string; paths: string[]; busy: boolean; error: string; onChoose: (choice: CloseChoice) => void;
  recovery?: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const element = dialog.current;
    element?.showModal();
    return () => { element?.close(); previous?.focus(); };
  }, []);
  return <dialog ref={dialog} className={styles.dialog} aria-labelledby="close-title"
    onCancel={event => { event.preventDefault(); if (!busy && !recovery) onChoose('cancel'); }}>
    <h2 id="close-title">{title}</h2>
    <p>还有未保存的修改。</p>
    <ul>{paths.map(path => <li key={path}>{path}</li>)}</ul>
    <p className={styles.hint}>保存会写入所有已打开内容。</p>
    {error && <p className={styles.error} role="alert">{error}</p>}
    <div className={styles.actions}>
      {recovery && <button disabled={busy} onClick={recovery}>查询原操作结果</button>}
      <button disabled={busy || Boolean(recovery)} onClick={() => onChoose('save')}>保存并继续</button>
      <button disabled={busy || Boolean(recovery)} onClick={() => onChoose('discard')}>放弃修改</button>
      <button disabled={busy || Boolean(recovery)} autoFocus onClick={() => onChoose('cancel')}>取消</button>
    </div>
  </dialog>;
}
