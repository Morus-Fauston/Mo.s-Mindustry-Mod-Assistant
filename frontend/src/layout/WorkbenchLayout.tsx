import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import type { WorkbenchLayout as LayoutState } from '../preferences/types';
import { resetWidth, resizeWidth, resolveLayout } from './geometry';
import { Separator } from './Separator';
import styles from './layout.module.css';

export interface WorkbenchLayoutProps {
  layout: LayoutState;
  onLayoutChange(next: LayoutState): void;
  files: ReactNode;
  editor: ReactNode;
  preview: ReactNode;
}

export function WorkbenchLayout({ layout, onLayoutChange, files, editor, preview }: WorkbenchLayoutProps) {
  const root = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    let active = true;
    const measure = () => { if (active) setWidth(element.getBoundingClientRect().width); };
    measure();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', measure);
      return () => { active = false; window.removeEventListener('resize', measure); };
    }
    const observer = new ResizeObserver(entries => {
      if (active && entries[0]) setWidth(entries[0].contentRect.width);
    });
    observer.observe(element);
    return () => { active = false; observer.disconnect(); };
  }, []);
  const measured = resolveLayout(width, layout);
  const style = { '--layout-left': `${measured.left}px`, '--layout-right': `${measured.right}px`,
    '--layout-left-separator': `${layout.filesVisible ? measured.separator : 0}px`,
    '--layout-right-separator': `${layout.previewVisible ? measured.separator : 0}px` } as CSSProperties;
  const separator = (side: 'left' | 'right') => {
    const value = side === 'left' ? measured.left : measured.right;
    const bounds = side === 'left' ? measured.leftBounds : measured.rightBounds;
    return <Separator orientation="vertical" label={side === 'left' ? '文件面板宽度' : '预览面板宽度'}
      value={value} min={measured.resizable ? bounds.min : value} max={measured.resizable ? bounds.max : value}
      disabled={!measured.resizable} direction={side === 'left' ? 1 : -1}
      onChange={next => onLayoutChange(resizeWidth(layout, side, next, width))}
      onReset={() => onLayoutChange(resetWidth(layout, side))} />;
  };
  return <div ref={root} className={styles.workbench} style={style} data-workbench-layout="true">
    <div className={`${styles.pane} ${styles.files}`} data-layout-panel="files" hidden={!layout.filesVisible}>{files}</div>
    {layout.filesVisible && <div className={styles.leftSeparator}>{separator('left')}</div>}
    <div className={`${styles.pane} ${styles.editor}`} data-layout-panel="editor">{editor}</div>
    {layout.previewVisible && <div className={styles.rightSeparator}>{separator('right')}</div>}
    <div className={`${styles.pane} ${styles.preview}`} data-layout-panel="preview" hidden={!layout.previewVisible}>{preview}</div>
  </div>;
}
