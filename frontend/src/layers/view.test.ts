import { describe, expect, it } from 'vitest';
import { flattenLayers, layerKeyAction, reconcileLayerView, revealLayerView } from './view';
import type { LayerNode, LayerViewState } from './types';

const a = 'weapon:' + 'a'.repeat(32), b = 'weapon:' + 'b'.repeat(32);
const nodes: LayerNode[] = [
  { id: 'sprite:', kind: 'sprite', label: '主体', drawableKeys: [''] },
  { id: 'group:weapons', kind: 'weapon-group', label: '武器', children: [
    { id: a, kind: 'weapon', label: '相同名称', drawableKeys: ['__weapon_0__'] },
    { id: b, kind: 'weapon', label: '相同名称', drawableKeys: ['__weapon_1__'] },
  ] },
];

describe('图层视图身份与键盘规则', () => {
  it('重排保留同一武器锚点，删除清理失效状态，不修改输入', () => {
    const state: LayerViewState = { selectedId: a, hiddenIds: [a, 'stale', a], closedIds: ['group:weapons', 'stale', a] };
    const reordered = [nodes[0], { ...nodes[1], children: [...nodes[1].children!].reverse() }];
    expect(reconcileLayerView(reordered, state)).toEqual({ selectedId: a, hiddenIds: [a], closedIds: ['group:weapons'] });
    expect(reconcileLayerView([nodes[0]], state)).toEqual({ selectedId: null, hiddenIds: [], closedIds: [] });
    expect(state.hiddenIds).toEqual([a, 'stale', a]);
  });

  it('定位打开所需祖先但保留隐藏状态，普通折叠不改变选择', () => {
    const state: LayerViewState = { selectedId: null, hiddenIds: [a], closedIds: ['group:weapons'] };
    expect(revealLayerView(nodes, state, a)).toEqual({ selectedId: a, hiddenIds: [a], closedIds: [] });
    expect(revealLayerView(nodes, state, 'stale')).toEqual(state);
    expect(flattenLayers(nodes, state.closedIds).map(row => row.node.id)).toEqual(['sprite:', 'group:weapons']);
    expect(flattenLayers(nodes, []).map(row => [row.node.id, row.depth, row.parentId])).toEqual([
      ['sprite:', 0, null], ['group:weapons', 0, null], [a, 1, 'group:weapons'], [b, 1, 'group:weapons'],
    ]);
  });

  it('方向键和首尾键只移动树焦点，空格显隐与回车选择保持正交', () => {
    const rows = flattenLayers(nodes, []);
    expect(layerKeyAction(rows, a, 'ArrowDown', [])).toEqual({ kind: 'focus', id: b });
    expect(layerKeyAction(rows, a, 'ArrowLeft', [])).toEqual({ kind: 'focus', id: 'group:weapons' });
    expect(layerKeyAction(rows, a, 'Home', [])).toEqual({ kind: 'focus', id: 'sprite:' });
    expect(layerKeyAction(rows, a, 'End', [])).toEqual({ kind: 'focus', id: b });
    expect(layerKeyAction(rows, a, ' ', [])).toEqual({ kind: 'visibility', id: a });
    expect(layerKeyAction(rows, a, 'Enter', [])).toEqual({ kind: 'select', id: a });
    expect(layerKeyAction(rows, 'group:weapons', 'ArrowLeft', [])).toEqual({ kind: 'expanded', id: 'group:weapons', expanded: false });
    const closed = flattenLayers(nodes, ['group:weapons']);
    expect(layerKeyAction(closed, 'group:weapons', 'ArrowRight', ['group:weapons'])).toEqual({ kind: 'expanded', id: 'group:weapons', expanded: true });
    expect(layerKeyAction(rows, 'group:weapons', ' ', [])).toBeNull();
  });
});
