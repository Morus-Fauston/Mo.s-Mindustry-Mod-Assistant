import type { FormField } from '../forms/types';
import type { ObjectPath } from '../nested/types';

/** Read-only response from PreviewLayerService; values remain Python-owned. */
export interface LayerNode {
  id: string;
  kind: 'sprite' | 'weapon-group' | 'weapon' | 'engine';
  label: string;
  status?: 'ready' | 'missing' | 'optional' | 'invalid';
  notice?: string;
  children?: LayerNode[];
  drawableKeys?: string[];
  weapon?: {
    itemId: string;
    objectPath: ObjectPath;
    coordinates: { x?: FormField; y?: FormField };
  };
}

export interface WeaponAnchor {
  sessionId: string;
  path: string;
  itemId: string;
  objectPath: ObjectPath;
}

export interface LayerViewState {
  selectedId: string | null;
  hiddenIds: string[];
  closedIds: string[];
}

export interface LayerRow {
  node: LayerNode;
  depth: number;
  parentId: string | null;
  position: number;
  siblings: number;
}
