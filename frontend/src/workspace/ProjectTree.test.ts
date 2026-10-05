import { createElement, isValidElement, type ReactElement, type ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { ProjectTree } from './ProjectTree';
import type { TreeNode } from './types';

const nodes: TreeNode[] = [
  { id: 'content', kind: 'group', label: '内容', children: [
    { id: 'unit', kind: 'content', label: '单位', path: 'content/units/test.json' },
  ] },
  { id: 'sprites', kind: 'group', label: '贴图', children: [
    { id: 'png', kind: 'sprite', label: '贴图文件', path: 'sprites/test.png' },
  ] },
];

function elements(node: ReactNode): ReactElement<Record<string, any>>[] {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!isValidElement<Record<string, any>>(node)) return [];
  return [node, ...elements(node.props.children)];
}

function render(disabled?: boolean) {
  const onOpen = vi.fn();
  let tree: ReactNode;
  // Capture the actual component's event handlers during a real React SSR render.
  // No browser-native disabled semantics are assumed in the handler assertions.
  function Capture() {
    tree = ProjectTree({ nodes, selectedPath: null, onOpen, ...(disabled === undefined ? {} : { disabled }) });
    return tree;
  }
  const html = renderToStaticMarkup(createElement(Capture));
  return { html, onOpen, all: elements(tree) };
}

describe('工程树临时禁用内容打开', () => {
  it('禁用内容和贴图叶按钮，分组折叠和搜索仍然可用', () => {
    const { html, all, onOpen } = render(true);
    const rows = all.filter(element => element.props.role === 'treeitem');
    expect(rows.filter(row => row.props['data-node-kind'] !== 'group').map(row => row.props.disabled)).toEqual([true, true]);
    expect(rows.filter(row => row.props['data-node-kind'] === 'group').every(row => !row.props.disabled)).toBe(true);
    expect(all.find(element => element.props['aria-label'] === '搜索文件')?.props.disabled).toBeUndefined();
    expect(html.match(/disabled=""/g)).toHaveLength(2);
    expect(onOpen).not.toHaveBeenCalled();
  });

  it('禁用期间即便调用真实点击或Enter/Space处理器也不打开叶节点', () => {
    const { all, onOpen } = render(true);
    for (const row of all.filter(element => element.props.role === 'treeitem' && element.props['data-node-kind'] !== 'group')) {
      row.props.onClick();
      for (const key of ['Enter', ' ']) {
        const preventDefault = vi.fn();
        row.props.onKeyDown({ key, preventDefault });
        expect(preventDefault).toHaveBeenCalledOnce();
      }
    }
    expect(onOpen).not.toHaveBeenCalled();
  });

  it('省略disabled保持原有点击和键盘打开行为', () => {
    const { all, onOpen, html } = render();
    const leaf = all.find(element => element.props['data-node-id'] === 'unit')!;
    leaf.props.onClick();
    leaf.props.onKeyDown({ key: 'Enter', preventDefault: vi.fn() });
    leaf.props.onKeyDown({ key: ' ', preventDefault: vi.fn() });
    expect(onOpen.mock.calls).toEqual([[nodes[0].children![0]], [nodes[0].children![0]], [nodes[0].children![0]]]);
    expect(html).not.toContain('disabled=""');
  });

  it('禁用叶期间方向键跳到下一可用分组而非停在不可聚焦叶', () => {
    const { all } = render(true);
    const rows = all.filter(element => element.props.role === 'treeitem');
    const targets = new Map(rows.map(row => [row.props['data-node-id'], { focus: vi.fn(), scrollIntoView: vi.fn() }]));
    for (const row of rows) row.props.ref(targets.get(row.props['data-node-id']));
    vi.stubGlobal('requestAnimationFrame', (callback: () => void) => callback());
    try {
      rows[0].props.onKeyDown({ key: 'ArrowDown', preventDefault: vi.fn() });
      expect(targets.get('sprites')!.focus).toHaveBeenCalledOnce();
      expect(targets.get('unit')!.focus).not.toHaveBeenCalled();
    } finally { vi.unstubAllGlobals(); }
  });
});
