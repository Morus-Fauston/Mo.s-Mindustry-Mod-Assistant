import type { LayerNode, LayerRow, LayerViewState } from './types';

export function flattenLayers(nodes: LayerNode[], closedIds: readonly string[]): LayerRow[] {
  const closed = new Set(closedIds), result: LayerRow[] = [];
  function visit(children: LayerNode[], depth: number, parentId: string | null) {
    children.forEach((node, index) => {
      result.push({ node, depth, parentId, position: index + 1, siblings: children.length });
      if (node.children && !closed.has(node.id)) visit(node.children, depth + 1, node.id);
    });
  }
  visit(nodes, 0, null);
  return result;
}

export function layerAncestors(nodes: LayerNode[], target: string): string[] | null {
  for (const node of nodes) {
    if (node.id === target) return [];
    if (node.children) {
      const found = layerAncestors(node.children, target);
      if (found) return [node.id, ...found];
    }
  }
  return null;
}

export function canToggleLayer(node: LayerNode): boolean {
  return node.kind !== 'weapon-group' || Boolean(node.drawableKeys?.length);
}

/** Prune view-only state after authoritative nodes change; never invent an item id. */
export function reconcileLayerView(nodes: LayerNode[], state: LayerViewState): LayerViewState {
  const rows = flattenLayers(nodes, []);
  const all = new Set(rows.map(row => row.node.id));
  const visible = new Set(rows.filter(row => canToggleLayer(row.node)).map(row => row.node.id));
  const branches = new Set(rows.filter(row => row.node.children).map(row => row.node.id));
  return {
    selectedId: state.selectedId && all.has(state.selectedId) ? state.selectedId : null,
    hiddenIds: [...new Set(state.hiddenIds)].filter(id => visible.has(id)),
    closedIds: [...new Set(state.closedIds)].filter(id => branches.has(id)),
  };
}

/** Explicit locate opens ancestors while preserving the user's visibility choice. */
export function revealLayerView(nodes: LayerNode[], state: LayerViewState, id: string): LayerViewState {
  const current = reconcileLayerView(nodes, state), ancestors = layerAncestors(nodes, id);
  return ancestors ? { ...current, selectedId: id, closedIds: current.closedIds.filter(value => !ancestors.includes(value)) } : current;
}

export type LayerKeyAction = { kind: 'focus' | 'select' | 'visibility'; id: string }
  | { kind: 'expanded'; id: string; expanded: boolean };

export function layerKeyAction(rows: LayerRow[], id: string, key: string, closedIds: readonly string[]): LayerKeyAction | null {
  const index = rows.findIndex(row => row.node.id === id), row = rows[index];
  if (!row) return null;
  const focus = (target: string | null | undefined): LayerKeyAction | null => target ? { kind: 'focus', id: target } : null;
  switch (key) {
    case 'ArrowDown': return focus(rows[Math.min(index + 1, rows.length - 1)]?.node.id);
    case 'ArrowUp': return focus(rows[Math.max(index - 1, 0)]?.node.id);
    case 'Home': return focus(rows[0]?.node.id);
    case 'End': return focus(rows.at(-1)?.node.id);
    case 'ArrowLeft': return row.node.children && !closedIds.includes(id)
      ? { kind: 'expanded', id, expanded: false } : focus(row.parentId);
    case 'ArrowRight': return row.node.children
      ? closedIds.includes(id) ? { kind: 'expanded', id, expanded: true }
        : focus(rows[index + 1]?.parentId === id ? rows[index + 1].node.id : null) : null;
    case 'Enter': return { kind: 'select', id };
    case ' ': return canToggleLayer(row.node) ? { kind: 'visibility', id } : null;
    default: return null;
  }
}
