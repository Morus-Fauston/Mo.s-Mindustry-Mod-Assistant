import { Fragment, useCallback, useEffect, useState } from 'react';
import { desktop, type BootstrapData } from './bridge/desktop';
import styles from './App.module.css';

type Startup = { phase: 'loading' } | { phase: 'ready'; data: BootstrapData } | { phase: 'error'; message: string };

const categoryLabels: Record<string, string> = {
  Units: '单位', UnitTypes: '单位', Blocks: '方块', Weapons: '武器', Bullets: '子弹',
  Items: '物品', Liquids: '液体', StatusEffects: '状态效果',
  Planets: '星球', Sectors: '战区', SectorPresets: '战区',
};

export function App() {
  const [startup, setStartup] = useState<Startup>({ phase: 'loading' });
  const load = useCallback(() => {
    setStartup({ phase: 'loading' });
    void desktop.bootstrap().then(data => setStartup({ phase: 'ready', data }))
      .catch((error: unknown) => setStartup({ phase: 'error', message: error instanceof Error ? error.message : '程序连接失败，请重试。' }));
  }, []);
  useEffect(load, [load]);
  const metadata = startup.phase === 'ready' ? startup.data.metadata : null;
  const status = startup.phase === 'ready' ? '离线元数据已就绪' : startup.phase === 'error' ? '启动未完成' : '正在连接桌面程序';

  return <div className={styles.app} data-startup={startup.phase}>
    <header className={styles.menu}>
      <span className={styles.brand}><span className={styles.mark}>M</span> MoMA</span>
      <span className={styles.caption}>模组助手</span>
    </header>
    <div className={styles.toolbar}><span className={styles.caption}>工作台</span><span>未打开工程</span></div>
    <main className={styles.workbench}>
      <aside className={styles.sidebar} aria-label="文件">
        <h2 className={styles.panelHead}>文件</h2>
        <p className={styles.emptySide}>尚未打开工程</p>
      </aside>
      <section className={styles.editor} aria-label="编辑区">
        <div className={styles.tabBar}><div className={styles.tab}>欢迎</div></div>
        <div className={styles.welcome}>
          <h1>模组工作台</h1>
          <p className={styles.description}>编辑内容，调整贴图，查看预览。</p>
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
        </div>
      </section>
      <aside className={styles.right} aria-label="预览与图层">
        <h2 className={styles.panelHead}>预览</h2>
        <div className={styles.preview}>选择内容后显示贴图</div>
        <h2 className={styles.panelHead}>图层</h2>
        <p className={styles.emptySide}>暂无图层</p>
      </aside>
    </main>
    <footer className={styles.status}><span role="status">{status}</span><span>{metadata ? `游戏版本 ${metadata.gameVersion}` : '离线工作台'}</span></footer>
  </div>;
}
