import { describe, expect, it } from 'vitest';
import { createPreferencesDrafts } from './drafts';
import type { PreferencesPatch, PreferencesState } from './types';

const state = (): PreferencesState => ({ revision: 0,
  defaults: { theme: 'light', display_name_mode: 'zh_en', auto_save_interval: 180, sprite_zoom: 4, mindustry_path: '旧字段' },
  values: { theme: 'light', display_name_mode: 'zh_en', auto_save_interval: 180, sprite_zoom: 4, mindustry_path: '必须保留' },
  layout: { leftWidth: null, rightWidth: null, previewRatio: null, filesVisible: true, previewVisible: true }, warnings: [] });
const deferred = () => { let resolve!: () => void, reject!: (error: Error) => void;
  const promise = new Promise<void>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };

describe('设置表单的提交边界', () => {
  it('超时后权威读回确认相同设置时清掉旧失败提示，不重复提交', async () => {
    const original = state(), drafts = createPreferencesDrafts(original);
    drafts.set('theme', 'dark');
    await drafts.apply(async () => { throw new Error('原请求结果未确认'); });
    expect(drafts.getSnapshot().error).toBeTruthy();
    drafts.sync({ ...original, revision: 1, values: { ...original.values, theme: 'dark' } });
    expect(drafts.getSnapshot().dirty).toBe(false);
    expect(drafts.getSnapshot().error).toBe('');
  });
  it('只发送四项中的修改，成功前保留草稿，写入失败保留原输入并允许重试', async () => {
    const drafts = createPreferencesDrafts(state()), pending = deferred();
    drafts.set('theme', 'dark'); drafts.set('auto_save_interval', '0');
    const patches: PreferencesPatch[] = [];
    const apply = drafts.apply(patch => { patches.push(patch); return pending.promise; });
    expect(patches).toEqual([{ theme: 'dark', auto_save_interval: 0 }]);
    expect(drafts.getSnapshot().pending).toBe(true);
    expect(drafts.getSnapshot().drafts).toEqual({ theme: 'dark', auto_save_interval: '0' });
    pending.reject(new Error('配置文件被占用。'));
    await expect(apply).resolves.toBe(false);
    expect(drafts.getSnapshot().error).toBe('配置文件被占用。');
    expect(drafts.getSnapshot().drafts).toEqual({ theme: 'dark', auto_save_interval: '0' });
    expect(await drafts.apply(async patch => { patches.push(patch); })).toBe(true);
    expect(drafts.getSnapshot().drafts).toEqual({});
    expect(drafts.getSnapshot().pending).toBe(false);
    expect(patches).toHaveLength(2);
  });
  it.each([
    ['auto_save_interval', ['', '-1', '3601', '1.5', '1e2', 'NaN', 'Infinity', '自动']],
    ['sprite_zoom', ['', '0', '9', '2.5', '2e0', '-2']],
    ['theme', ['LIGHT', 'system', '']], ['display_name_mode', ['cn', 'zh-en', '']],
  ] as const)('%s只接受后端允许的范围与离散值', async (key, values) => {
    for (const value of values) {
      const drafts = createPreferencesDrafts(state()); let calls = 0;
      drafts.set(key, value);
      expect(await drafts.apply(async () => { calls++; })).toBe(false);
      expect(calls).toBe(0); expect(drafts.getSnapshot().errors[key]).toBeTruthy();
      expect(drafts.getSnapshot().drafts[key]).toBe(value);
    }
  });
  it('包含端点的整数合法，四种显示模式都直接传递既有标识', async () => {
    for (const [key, value] of [['auto_save_interval', '0'], ['auto_save_interval', '3600'], ['sprite_zoom', '1'], ['sprite_zoom', '8'],
      ['display_name_mode', 'zh_en'], ['display_name_mode', 'en_zh'], ['display_name_mode', 'zh'], ['display_name_mode', 'en']] as const) {
      const drafts = createPreferencesDrafts(state()); drafts.set(key, value);
      expect(drafts.getSnapshot().errors).toEqual({});
      expect(await drafts.apply(async patch => { expect(patch[key]).toBe(key === 'display_name_mode' ? value : Number(value)); })).toBe(true);
    }
  });
  it('同一提交期间双击只调用一次，成功不清除稍后产生的新输入', async () => {
    const drafts = createPreferencesDrafts(state()), pending = deferred(); let calls = 0;
    drafts.set('auto_save_interval', '45');
    const first = drafts.apply(async () => { calls++; await pending.promise; });
    expect(await drafts.apply(async () => { calls++; })).toBe(false);
    drafts.set('auto_save_interval', '90');
    pending.resolve(); expect(await first).toBe(true);
    expect(calls).toBe(1); expect(drafts.getSnapshot().drafts.auto_save_interval).toBe('90');
  });
  it('同一配置的新修订仅刷新未编辑项，恢复默认读取真实defaults且不发送旧键', async () => {
    const initial = state(); initial.defaults.sprite_zoom = 6;
    const drafts = createPreferencesDrafts(initial);
    drafts.set('auto_save_interval', '30');
    drafts.sync({ ...initial, revision: 2, values: { ...initial.values, theme: 'dark', sprite_zoom: 7 } });
    expect(drafts.getSnapshot().text).toMatchObject({ auto_save_interval: '30', theme: 'dark', sprite_zoom: '7' });
    drafts.sync(initial);
    expect(drafts.getSnapshot().text.theme).toBe('dark');
    drafts.resetDefaults();
    expect(drafts.getSnapshot().text.sprite_zoom).toBe('6');
    const patches: PreferencesPatch[] = [];
    await drafts.apply(async patch => { patches.push(patch); });
    expect(patches).toEqual([{ theme: 'light', sprite_zoom: 6 }]);
    expect(initial.values.mindustry_path).toBe('必须保留');
  });
  it.each(['resolve', 'reject'] as const)('面板关闭后%s迟到结果不能通知或清除新生命周期草稿', async outcome => {
    const drafts = createPreferencesDrafts(state()), pending = deferred(); let notifications = 0;
    drafts.subscribe(() => notifications++);
    drafts.set('theme', 'dark'); const first = drafts.apply(() => pending.promise);
    drafts.setActive(false);
    const closedCount = notifications;
    drafts.set('theme', 'light');
    expect(notifications).toBe(closedCount);
    drafts.setActive(true); drafts.set('sprite_zoom', '8');
    const before = drafts.getSnapshot(), activeCount = notifications;
    if (outcome === 'resolve') pending.resolve(); else pending.reject(new Error('旧窗口失败'));
    expect(await first).toBe(false);
    expect(drafts.getSnapshot()).toBe(before); expect(notifications).toBe(activeCount);
    expect(drafts.getSnapshot().error).toBe('');
    expect(drafts.getSnapshot().drafts.sprite_zoom).toBe('8');
  });
});
