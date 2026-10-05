import { useEffect, useId, useRef, useState, useSyncExternalStore } from 'react';
import { createComparisonController } from './controller';
import { valueKindLabels, type Comparison, type ComparisonCallbacks, type ComparisonCell } from './types';
import styles from './ReferenceComparison.module.css';

export type { SourceDescriptor, CandidatePage, Comparison, ComparisonCell, ReferenceSelection } from './types';
export interface ReferenceComparisonProps extends ComparisonCallbacks {
  sessionId: string;
  path: string;
  revision: number;
  fieldNames: Record<string, string>;
  fieldDocs: Record<string, string>;
  disabled: boolean;
  compareDisabled?: boolean;
}

export function ReferenceComparison(props: ReferenceComparisonProps) {
  return <ReferencePanel key={props.sessionId} {...props} />;
}

function ReferencePanel(props: ReferenceComparisonProps) {
  const [controller] = useState(createComparisonController);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  const [sourceId, setSourceId] = useState(''), [category, setCategory] = useState('');
  const [query, setQuery] = useState(''), [searchedQuery, setSearchedQuery] = useState('');
  const [name, setName] = useState('');
  const id = useId(), initialCandidates = useRef('');
  const initialized = state.sessionId === props.sessionId;
  const locked = props.disabled || !initialized || Boolean(state.busy);
  const selectedSource = state.sources.find(source => source.sourceId === sourceId);
  const page = state.page?.sourceId === sourceId && state.page.category === category ? state.page : null;

  useEffect(() => {
    controller.start(props.sessionId, props.path, props.revision, props);
    void controller.loadSources();
    return () => controller.stop();
  }, [controller, props.sessionId]);

  useEffect(() => { controller.updateContext(props.path, props.revision, props, !props.disabled && !props.compareDisabled); });

  useEffect(() => {
    if (state.sources.some(item => item.sourceId === sourceId)) return;
    const source = state.sources.find(item => item.sourceId === state.selection?.sourceId) ?? state.sources[0];
    if (!source) return;
    if (source.sourceId !== sourceId) {
      setSourceId(source.sourceId); setCategory(source.categories[0]?.id ?? ''); setQuery(''); setName('');
    }
  }, [state.sources, state.selection, sourceId]);

  useEffect(() => {
    if (!state.pending) return;
    setSourceId(state.pending.sourceId); setCategory(state.pending.categories[0]?.id ?? ''); setQuery(''); setName('');
  }, [state.pending]);

  useEffect(() => {
    if (locked || !sourceId || !category) return;
    const key = JSON.stringify([sourceId, category]);
    if (initialCandidates.current === key) return;
    initialCandidates.current = key;
    setSearchedQuery(''); setName('');
    void controller.candidates(sourceId, category, '', 0);
  }, [controller, sourceId, category, locked]);

  useEffect(() => { setName(page?.candidates[0]?.name ?? ''); }, [page]);

  function chooseSource(value: string) {
    const source = state.sources.find(item => item.sourceId === value);
    setSourceId(value); setCategory(source?.categories[0]?.id ?? ''); setName(''); setQuery('');
  }
  function search(offset = 0, needle = query) {
    if (locked || !sourceId || !category) return;
    setSearchedQuery(needle); setName('');
    void controller.candidates(sourceId, category, needle, offset);
  }

  return <section className={styles.panel} aria-labelledby={`${id}-title`} aria-busy={Boolean(state.busy)}>
    <header className={styles.heading}><h2 id={`${id}-title`}>只读参考与内容对比</h2><span>只读</span></header>
    <div className={styles.body}>
      <div className={styles.actions}>
        <button className={styles.action} type="button" disabled={locked || Boolean(state.pending)}
          onClick={() => void controller.open('folder')}>打开参考目录</button>
        <button className={styles.action} type="button" disabled={locked || Boolean(state.pending)}
          onClick={() => void controller.open('zip')}>打开参考压缩包</button>
      </div>
      <div className={styles.row}>
        <label htmlFor={`${id}-source`}>参考来源</label>
        <div className={styles.control} data-field-type="ref"><select id={`${id}-source`} value={sourceId} disabled={locked}
          onChange={event => chooseSource(event.target.value)}>
          {!state.sources.length && <option value="">尚未读取来源</option>}
          {state.sources.map(source => <option key={source.sourceId} value={source.sourceId}>
            {source.label}{source.sourceId === state.pending?.sourceId ? '（待确认）' : ''}
          </option>)}
        </select></div>
      </div>
      <div className={styles.row}>
        <label htmlFor={`${id}-category`}>内容类别</label>
        <div className={styles.control} data-field-type="ref"><select id={`${id}-category`} value={category}
          disabled={locked || !selectedSource?.categories.length} onChange={event => {
            setCategory(event.target.value); setQuery(''); setName('');
          }}>
          {!selectedSource?.categories.length && <option value="">没有可选类别</option>}
          {selectedSource?.categories.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select></div>
      </div>
      <form className={styles.search} onSubmit={event => { event.preventDefault(); search(); }}>
        <label htmlFor={`${id}-query`}>搜索参考内容</label>
        <div className={styles.searchControls}>
          <div className={styles.control} data-field-type="str"><input id={`${id}-query`} type="text" maxLength={256}
            value={query} disabled={locked || !category} placeholder="输入中文名称或英文标识"
            onChange={event => setQuery(event.target.value)} /></div>
          <button type="submit" className={styles.action} disabled={locked || !category}>搜索</button>
        </div>
      </form>
      <div className={styles.candidates}>
        <label htmlFor={`${id}-candidate`}>参考内容</label>
        <div className={styles.control} data-field-type="ref"><select id={`${id}-candidate`} size={5} value={name}
          disabled={locked || !page?.candidates.length} onChange={event => setName(event.target.value)}>
          {!page?.candidates.length && <option value="">{state.busy === 'candidates' ? '正在读取候选…' : '没有匹配内容'}</option>}
          {page?.candidates.map(item => <option key={item.name} value={item.name}>{item.label}</option>)}
        </select></div>
        {page && <div className={styles.pagination}>
          <span>{page.total ? `${page.offset + 1}–${page.offset + page.candidates.length} / ${page.total} 项` : '共 0 项'}
            {searchedQuery ? `；搜索：${searchedQuery}` : ''}</span>
          <button type="button" className={styles.action} disabled={locked || page.offset === 0} onClick={() => search(Math.max(0, page.offset - 100), searchedQuery)}>上一页</button>
          <button type="button" className={styles.action} disabled={locked || !page.hasMore} onClick={() => search(page.offset + 100, searchedQuery)}>下一页</button>
        </div>}
      </div>
      <div className={styles.actions}>
        <button type="button" className={styles.action} disabled={locked || props.compareDisabled || !name || !props.path}
          onClick={() => void controller.compare(sourceId, category, name)}>确认比较</button>
        {state.pending && <button type="button" className={styles.action} disabled={locked}
          onClick={() => void controller.cancelPending()}>取消待选参考</button>}
        {state.comparison && <button type="button" className={styles.action} disabled={locked || props.compareDisabled || !props.path}
          onClick={() => void controller.refresh()}>刷新当前对比</button>}
      </div>
      {!props.path && <p className={styles.status}>请先打开一个内容文件，再确认比较。</p>}
      {!!selectedSource?.warnings.length && <ul className={styles.warnings} aria-label="参考读取提示">
        {selectedSource.warnings.map((warning, index) => <li key={index}>{warning}</li>)}
      </ul>}
      {state.stale && <p className={styles.status} role="status">当前文件或内容已变化，以下仍为上次结果；正在重新读取，失败时请刷新。</p>}
      {state.error && <p className={styles.error} role="alert">{state.error}</p>}
      {state.cleanupNeeded && <button type="button" className={styles.action} disabled={locked}
        onClick={() => void controller.retryCleanup()}>重试清理未使用来源</button>}
      {!state.sources.length && !state.busy && initialized && <button type="button" className={styles.action} disabled={props.disabled}
        onClick={() => void controller.loadSources()}>重新读取来源</button>}
      {state.busy && <p className={styles.status} role="status">{state.busy === 'open' ? '正在选择并读取参考…'
        : state.busy === 'compare' ? '正在读取当前内容并比较…' : state.busy === 'cancel' || state.busy === 'cleanup' ? '正在释放参考来源…' : '正在读取参考列表…'}</p>}
      {state.notice && <p className={styles.status} role="status">{state.notice}</p>}
      {state.comparison && <ComparisonTable comparison={state.comparison} fieldNames={props.fieldNames} fieldDocs={props.fieldDocs} />}
    </div>
  </section>;
}

export function ComparisonTable({ comparison, fieldNames, fieldDocs }: {
  comparison: Comparison; fieldNames: Record<string, string>; fieldDocs: Record<string, string>;
}) {
  const differenceCount = comparison.rows.filter(row => row.different).length;
  function cell(value: ComparisonCell) {
    return <><span className={styles.value}>{value.text}</span>
      <span className={styles.kind}>{valueKindLabels[value.kind]}{value.truncated ? '；显示已截断' : ''}</span></>;
  }
  return <div className={styles.comparison}>
    <p className={styles.status}>当前文件：{comparison.currentPath}</p>
    <p className={styles.status}>参考：{comparison.category} / {comparison.name}；共 {comparison.rows.length} 个字段，{differenceCount} 项不同。</p>
    <div className={styles.tableScroll} tabIndex={0} role="region" aria-label="只读字段对比，可横向滚动">
      <table className={styles.table}><caption>实际字段对比</caption><thead><tr><th scope="col">字段</th><th scope="col">我的值</th><th scope="col">参考值</th></tr></thead>
        <tbody>{comparison.rows.map(row => <tr key={row.field} data-different={row.different ? 'true' : 'false'}>
          <th scope="row" data-field={row.field} title={fieldDocs[row.field] ?? ''}>{fieldNames[row.field] ?? row.field}
            {row.different && <span className={styles.kind}>不同</span>}</th>
          <td>{cell(row.current)}</td><td>{cell(row.reference)}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <p className={styles.status}>仅比较实际顶层字段；对象和列表按完整内容判断差异，表内显示摘要。</p>
  </div>;
}
