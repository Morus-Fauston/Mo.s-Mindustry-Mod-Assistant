import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { PreferencesPanel } from './PreferencesPanel';
import type { PreferencesState } from './types';

const state: PreferencesState = { revision: 3,
  values: { theme: 'dark', display_name_mode: 'en_zh', auto_save_interval: 27, sprite_zoom: 6, mindustry_path: 'private-path', bullet_type_count: 5 },
  defaults: { theme: 'light', display_name_mode: 'zh_en', auto_save_interval: 180, sprite_zoom: 4 },
  layout: { leftWidth: null, rightWidth: null, previewRatio: null, filesVisible: true, previewVisible: true }, warnings: [] };

describe('设置对话框的受控展示', () => {
  it('只呈现四个可用设置，当前值来自props，渲染不写设置或泄漏保留键', () => {
    const onUpdate = vi.fn(async () => {}), onClose = vi.fn();
    const html = renderToStaticMarkup(createElement(PreferencesPanel, { state, busy: false, error: '', onUpdate, onClose }));
    for (const label of ['主题', '字段显示名', '自动保存间隔', '预览倍率']) expect(html).toContain(label);
    expect(html).toContain('value="dark" selected=""'); expect(html).toContain('value="en_zh" selected=""');
    expect(html).toContain('value="27"'); expect(html).toContain('value="6"');
    expect(html).not.toContain('private-path'); expect(html).not.toContain('bullet_type_count');
    expect((html.match(/<(?:input|select)\b/g) ?? [])).toHaveLength(4);
    expect(onUpdate).not.toHaveBeenCalled(); expect(onClose).not.toHaveBeenCalled();
  });
  it('显示后端读写反馈，忙碌时禁用关闭与输入，保留无emoji中文文案', () => {
    const html = renderToStaticMarkup(createElement(PreferencesPanel, { state: { ...state, warnings: ['默认配置无法读取，已使用安全值。'] },
      busy: true, error: '设置写入失败。', onUpdate: async () => {}, onClose: () => {} }));
    expect(html).toContain('默认配置无法读取'); expect(html).toContain('设置写入失败');
    expect(html).toContain('aria-busy="true"'); expect(html).toContain('role="alert"');
    expect((html.match(/<(?:input|select)[^>]*disabled=""/g) ?? [])).toHaveLength(4);
  });
});
