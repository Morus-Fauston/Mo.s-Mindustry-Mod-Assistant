import type { ObjectPath } from './types';

export interface NestedFocusRequest { token: number; objectPath: ObjectPath; field: string }

/** App tokens increase monotonically. Keep one tracker above collapsible controls. */
export function createNestedRevealTracker() {
  const consumed = new Set<string>();
  let latest: number | undefined;
  return {
    consume(request: NestedFocusRequest | undefined, container: ObjectPath, disabled: boolean): boolean {
      if (!request || disabled || !Number.isSafeInteger(request.token) || latest !== undefined && request.token < latest) return false;
      const target = [...request.objectPath, request.field];
      if (container.length > target.length || !container.every((segment, index) => {
        const candidate = target[index];
        return typeof segment === 'string' ? segment === candidate
          : typeof candidate === 'object' && segment.itemId === candidate.itemId;
      })) return false;
      if (request.token !== latest) { consumed.clear(); latest = request.token; }
      const key = JSON.stringify(container);
      if (consumed.has(key)) return false;
      consumed.add(key);
      return true;
    },
  };
}
