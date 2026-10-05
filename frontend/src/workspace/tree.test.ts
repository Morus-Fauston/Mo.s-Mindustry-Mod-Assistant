import { describe, expect, it } from 'vitest';
import type { TreeNode } from './types';
import { filterTree, flattenTree, expandedGroups, ancestorIds } from './tree';

const nodes: TreeNode[] = [
  { id: 'units', kind: 'group', label: '单位', children: [
    { id: 'u1', kind: 'content', label: '铜星', name: 'copper-star', path: 'content/units/star.json' },
    { id: 'u2', kind: 'content', label: '长弓', name: 'longbow', path: 'content/units/bow.json' },
  ] },
  { id: 'blocks', kind: 'group', label: '方块', children: [
    { id: 'turrets', kind: 'group', label: '炮塔', children: [
      { id: 'b1', kind: 'content', label: '铜星', name: 'duo', path: 'content/blocks/star.json' },
    ] },
  ] },
];

describe('工程树可见节点', () => {
  it('折叠子树不参与上下移动，展开后保持同名文件的路径身份与层级', () => {
    expect(flattenTree(nodes, new Set(['blocks'])).map(row => row.node.id))
      .toEqual(['units', 'blocks', 'turrets']);
    const rows = flattenTree(nodes, expandedGroups(nodes));
    expect(rows.map(row => row.node.id)).toEqual(['units', 'u1', 'u2', 'blocks', 'turrets', 'b1']);
    expect(rows.at(-1)).toMatchObject({ depth: 2, parentId: 'turrets', position: 1, siblings: 1 });
    expect(ancestorIds(nodes, 'content/blocks/star.json')).toEqual(['blocks', 'turrets']);
  });

  it('按显示名或内部名称过滤并保留祖先，大小写不敏感且不修改原树', () => {
    const filtered = filterTree(nodes, ' COPPER ');
    expect(flattenTree(filtered, expandedGroups(filtered)).map(row => row.node.id)).toEqual(['units', 'u1']);
    const chinese = filterTree(nodes, '铜星');
    expect(flattenTree(chinese, expandedGroups(chinese)).map(row => row.node.id)).toEqual(['units', 'u1', 'blocks', 'turrets', 'b1']);
    expect(nodes[0].children).toHaveLength(2);
    expect(filterTree(nodes, '')).toBe(nodes);
    expect(filterTree(nodes, '不存在')).toEqual([]);
  });

  it('搜索期间独立展开匹配祖先，清空仍可恢复原折叠集合', () => {
    const originalExpanded = new Set(['units']);
    const filtered = filterTree(nodes, '炮塔');
    expect(flattenTree(filtered, expandedGroups(filtered)).map(row => row.node.id))
      .toEqual(['blocks', 'turrets', 'b1']);
    expect(flattenTree(filterTree(nodes, ''), originalExpanded).map(row => row.node.id))
      .toEqual(['units', 'u1', 'u2', 'blocks']);
    expect(ancestorIds(nodes, 'missing.json')).toEqual([]);
  });
});
