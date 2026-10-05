import type { TreeNode } from './types';

export interface TreeRow {
  node: TreeNode;
  depth: number;
  parentId: string | null;
  position: number;
  siblings: number;
}

export function filterTree(nodes: TreeNode[], search: string): TreeNode[] {
  const query = search.trim().toLocaleLowerCase();
  if (!query) return nodes;
  return nodes.flatMap(node => {
    if ([node.label, node.name ?? ''].some(value => value.toLocaleLowerCase().includes(query))) return [node];
    const children = node.children && filterTree(node.children, query);
    return children?.length ? [{ ...node, children }] : [];
  });
}

export function expandedGroups(nodes: TreeNode[]): Set<string> {
  const result = new Set<string>();
  for (const node of nodes) {
    if (node.kind === 'group') result.add(node.id);
    if (node.children) for (const id of expandedGroups(node.children)) result.add(id);
  }
  return result;
}

export function flattenTree(nodes: TreeNode[], expanded: ReadonlySet<string>, depth = 0, parentId: string | null = null): TreeRow[] {
  return nodes.flatMap((node, index) => [
    { node, depth, parentId, position: index + 1, siblings: nodes.length },
    ...(node.children && expanded.has(node.id) ? flattenTree(node.children, expanded, depth + 1, node.id) : []),
  ]);
}

export function ancestorIds(nodes: TreeNode[], path: string): string[] {
  return findAncestors(nodes, path) ?? [];
}

function findAncestors(nodes: TreeNode[], path: string): string[] | null {
  for (const node of nodes) {
    if (node.path === path) return [];
    if (node.children) {
      const child = findAncestors(node.children, path);
      if (child) return [node.id, ...child];
    }
  }
  return null;
}
