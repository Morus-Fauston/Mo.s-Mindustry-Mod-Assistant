import { useEffect, useId, useRef, useState, useSyncExternalStore } from 'react';
import type { SpriteTarget } from '../resources/types';
import { createGenerationController } from './controller';
import { defaultParameters, generationOutputs, generationParametersError, parameterKeys, supportedTargets,
  type GenerationCallbacks, type GenerationParameters } from './types';
import styles from './SpriteGeneration.module.css';

export type { GenerationCandidate, GenerationOutput } from './types';
export interface SpriteGenerationProps extends GenerationCallbacks {
  sessionId: string;
  path: string;
  revision: number;
  disabled: boolean;
  targets: SpriteTarget[];
  fieldNames: Record<string, string>;
  fieldDocs: Record<string, string>;
}

export function SpriteGeneration(props: SpriteGenerationProps) {
  const identity = JSON.stringify([props.sessionId, props.path, props.revision]);
  // A revision change invalidates the candidate's source snapshot as well as its
  // component state. The outgoing controller still releases through old callbacks.
  return <GenerationPanel key={identity} {...props} identity={identity} />;
}

function GenerationPanel(props: SpriteGenerationProps & { identity: string }) {
  const targets = supportedTargets(props.targets);
  const [controller] = useState(createGenerationController);
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot, controller.getSnapshot);
  const [selected, setSelected] = useState<string[]>(() => targets[0] ? [targets[0].suffix] : []);
  const [parameters, setParameters] = useState<GenerationParameters>(() => ({ ...defaultParameters }));
  const [errors, setErrors] = useState<Partial<Record<keyof GenerationParameters, string>>>({});
  const [error, setError] = useState('');
  const [overwrite, setOverwrite] = useState(false);
  const titleId = useId(), prefix = useId();
  const previewButton = useRef<HTMLButtonElement>(null), cancelButton = useRef<HTMLButtonElement>(null);
  const hadCandidate = useRef(false);
  const current = state.identity === props.identity;
  const candidate = current ? state.candidate : null;
  const pending = !current || Boolean(state.busy);
  const locked = props.disabled || pending;
  const optionsLocked = locked || Boolean(candidate);
  const supportedKey = JSON.stringify(targets.map(target => target.suffix));
  const hasOverwrite = candidate?.outputs.some(output => output.exists) ?? false;

  useEffect(() => {
    controller.start(props.identity, props.sessionId, { onPreview: props.onPreview, onConfirm: props.onConfirm, onCancel: props.onCancel });
    return () => controller.stop();
  }, [controller, props.identity, props.sessionId]);

  useEffect(() => {
    const available: string[] = JSON.parse(supportedKey);
    setSelected(previous => {
      const keep = previous.filter(suffix => available.includes(suffix));
      return keep.length ? keep : available.slice(0, 1);
    });
  }, [supportedKey]);

  useEffect(() => {
    if (pending) return;
    if (candidate) { hadCandidate.current = true; cancelButton.current?.focus({ preventScroll: true }); }
    else if (hadCandidate.current) { hadCandidate.current = false; setOverwrite(false); previewButton.current?.focus({ preventScroll: true }); }
  }, [candidate, pending]);

  async function preview() {
    if (optionsLocked) return;
    const allowedSelected = targets.filter(target => selected.includes(target.suffix)).map(target => target.suffix);
    setErrors(generationParametersError(allowedSelected, parameters)); setError(''); setOverwrite(false);
    try { await controller.preview(generationOutputs(props.targets, selected, parameters)); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '生成参数无效。'); }
  }

  function parameter(name: keyof GenerationParameters, fieldType: 'num' | 'col') {
    const key = parameterKeys[name], id = `${prefix}-${name}`;
    const label = props.fieldNames[key] ?? '生成参数';
    return <div className={styles.parameter} key={name}>
      <label htmlFor={id} title={props.fieldDocs[key] ?? ''}>{label}</label>
      <div className={styles.parameterValue}>
        <div className={styles.control} data-field-type={fieldType}>
          <input id={id} type="text" aria-label={label} aria-invalid={Boolean(errors[name])}
            aria-describedby={errors[name] ? `${id}-error` : props.fieldDocs[key] ? `${id}-help` : undefined}
            inputMode={fieldType === 'num' ? 'numeric' : 'text'} disabled={optionsLocked} value={parameters[name]}
            onChange={event => { const value = event.target.value; setParameters(previous => ({ ...previous, [name]: value }));
              setErrors(previous => ({ ...previous, [name]: undefined })); setError(''); }} />
        </div>
        {errors[name] ? <p className={styles.error} id={`${id}-error`} role="alert">{errors[name]}</p>
          : props.fieldDocs[key] && <p className={styles.help} id={`${id}-help`}>{props.fieldDocs[key]}</p>}
      </div>
    </div>;
  }

  return <section className={styles.generation} aria-labelledby={titleId} aria-busy={pending}>
    <header className={styles.heading}><h2 id={titleId}>贴图生成</h2></header>
    {!targets.length ? <p className={styles.status}>当前内容没有可生成的贴图类型。</p> : <div className={styles.body}>
      <fieldset className={styles.options} disabled={optionsLocked}>
        <legend>生成结果</legend>
        {targets.map(target => <label className={styles.choice} key={target.suffix}>
          <input type="checkbox" checked={selected.includes(target.suffix)} onChange={event => {
            const checked = event.target.checked;
            setSelected(previous => checked ? [...previous, target.suffix] : previous.filter(suffix => suffix !== target.suffix)); setError('');
          }} /><span>{target.label}</span>
        </label>)}
      </fieldset>
      {selected.includes('-outline') && <>{parameter('expandPx', 'num')}{parameter('color', 'col')}</>}
      {selected.includes('-shadow') && parameter('opacity', 'num')}
      {!candidate && <button ref={previewButton} type="button" className={styles.action} disabled={optionsLocked || !selected.length}
        onClick={() => void preview()}>预览生成结果</button>}
      {candidate && <div className={styles.candidate} aria-label="生成候选" onKeyDown={event => {
        if (event.key === 'Escape' && !locked) { event.preventDefault(); event.stopPropagation(); void controller.cancel(); }
      }}>
        <p className={styles.status}>以下为预览候选，确认后才写入工程。</p>
        <ul className={styles.results}>{candidate.outputs.map(output => <li key={output.path} className={styles.result}>
          <div className={styles.imageFrame}>
            {output.dataUrl.startsWith('data:image/png;base64,')
              ? <img src={output.dataUrl} alt={`${output.label}生成预览`} width={output.width} height={output.height} />
              : <p className={styles.error}>预览图像格式无效，请取消后重试。</p>}
          </div>
          <div className={styles.description}><strong>{output.label}</strong>
            <span className={styles.filename} title={output.path}>{output.path}</span>
            <span>{output.width} × {output.height} 像素</span>
            <span>{output.exists ? '将覆盖已有贴图' : '将创建新贴图'}</span>
          </div>
        </li>)}</ul>
        {hasOverwrite && <label className={styles.overwrite}>
          <input type="checkbox" checked={overwrite} disabled={locked} onChange={event => setOverwrite(event.target.checked)} />
          <span>我确认覆盖以上标记为已有的贴图</span>
        </label>}
        <div className={styles.actions}>
          <button type="button" className={styles.action} disabled={locked || hasOverwrite && !overwrite}
            onClick={() => void controller.confirm(hasOverwrite && overwrite)}>{hasOverwrite ? '确认覆盖并写入' : '确认写入工程'}</button>
          <button ref={cancelButton} type="button" className={styles.action} disabled={locked} onClick={() => void controller.cancel()}>取消预览</button>
        </div>
      </div>}
      {(error || current && state.error) && <p className={styles.error} role="alert">{error || state.error}</p>}
      {current && state.busy && <p className={styles.status} role="status">{state.busy === 'preview' ? '正在生成预览…' : state.busy === 'confirm' ? '正在写入贴图…' : '正在取消预览…'}</p>}
      {current && state.confirmed && <p className={styles.status} role="status">贴图已写入工程，可通过撤销恢复。</p>}
    </div>}
  </section>;
}
