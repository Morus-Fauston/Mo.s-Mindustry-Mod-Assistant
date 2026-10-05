import type { DynamicAction, DynamicPreviewDescriptor, DynamicPreviewState } from './types';
import styles from './DynamicControls.module.css';

export interface DynamicControlsProps {
  descriptor: DynamicPreviewDescriptor | null;
  state: DynamicPreviewState;
  disabled?: boolean;
  onAction: (action: DynamicAction) => void;
}

/** Controlled view options, never business field edits. */
export function DynamicControls({ descriptor, state, disabled = false, onAction }: DynamicControlsProps) {
  const unavailable = disabled || !descriptor?.supported;
  return <section className={styles.controls} aria-label="动态预览" data-dynamic-enabled={state.enabled} data-dynamic-paused={state.paused}>
    <div className={styles.toolbar} role="toolbar" aria-label="动态预览操作">
      <button className={styles.button} disabled={unavailable} aria-pressed={state.enabled}
        onClick={() => onAction({ type: state.enabled ? 'stop' : 'start' })}>{state.enabled ? '结束预览' : '开始预览'}</button>
      <button className={styles.button} disabled={unavailable || !state.enabled} aria-pressed={state.paused}
        onClick={() => onAction({ type: 'togglePause' })}>{state.paused ? '继续播放' : '暂停帧'}</button>
      <button className={styles.button} disabled={unavailable || !state.enabled || !state.paused}
        onClick={() => onAction({ type: 'step' })}>单步</button>
      <button className={styles.button} disabled={unavailable || !state.enabled}
        onClick={() => onAction({ type: 'fire' })}>开火一次</button>
      <button className={styles.button} disabled={disabled} onClick={() => onAction({ type: 'reset' })}>复位</button>
    </div>
    {state.enabled && <div className={styles.options}>
      <label className={styles.option}>移动
        <select aria-label="预览移动" data-field-type="str" value={state.moving ? 'moving' : 'still'} disabled={unavailable}
          onChange={event => onAction({ type: 'moving', value: event.target.value === 'moving' })}>
          <option value="still">原地</option><option value="moving">移动</option>
        </select>
      </label>
      <label className={styles.option}>速度
        <select aria-label="预览速度" data-field-type="num" value={state.speed} disabled={unavailable}
          onChange={event => onAction({ type: 'speed', value: Number(event.target.value) as 0.5 | 1 | 2 })}>
          <option value={0.5}>0.5 倍</option><option value={1}>1 倍</option><option value={2}>2 倍</option>
        </select>
      </label>
      <label className={styles.option}>朝向
        <select aria-label="预览朝向" data-field-type="str" value={state.direction} disabled={unavailable}
          onChange={event => onAction({ type: 'direction', value: event.target.value })}>
          {descriptor?.directions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <label className={styles.option}>队伍
        <select aria-label="预览队伍" data-field-type="str" value={state.team} disabled={unavailable}
          onChange={event => onAction({ type: 'team', value: event.target.value })}>
          {descriptor?.teams.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <label className={styles.option}>生命值
        <select aria-label="预览生命值" data-field-type="str" value={state.health} disabled={unavailable}
          onChange={event => onAction({ type: 'health', value: event.target.value })}>
          {descriptor?.healthLevels.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
      <output className={styles.time} aria-label="预览模拟时间">{(state.animation.timeTick / 60).toFixed(2)} 秒</output>
    </div>}
    {descriptor?.notices.map((notice, index) => <p key={index} className={styles.notice}>{notice}</p>)}
  </section>;
}
