/** Logical cancellation only: the transport owns its real request resources. */
export function createLatestRequest() {
  let generation = 0;
  return {
    invalidate() { generation++; },
    async run<T>(load: () => Promise<T>): Promise<{ current: true; value: T } | { current: false }> {
      const current = ++generation;
      try {
        const value = await load();
        return current === generation ? { current: true, value } : { current: false };
      } catch (error) {
        if (current !== generation) return { current: false };
        throw error;
      }
    },
  };
}

export function moveCandidateIndex(current: number, direction: number, count: number): number {
  if (!count) return -1;
  if (current < 0) return direction > 0 ? 0 : count - 1;
  return Math.max(0, Math.min(count - 1, current + direction));
}

export interface PopupGeometry { left: number; top: number; width: number; height: number }

export function popupGeometry(anchor: { left: number; top: number; bottom: number; width: number },
  viewportWidth: number, viewportHeight: number): PopupGeometry {
  const width = Math.max(0, Math.min(Math.max(360, anchor.width), viewportWidth - 16));
  const height = Math.max(0, Math.min(380, viewportHeight - 16));
  const below = viewportHeight - anchor.bottom - 12;
  const above = anchor.top - 12;
  // Small viewports may overlap the anchor; the complete selector stays reachable.
  const desiredTop = below >= height ? anchor.bottom + 4 : above >= height ? anchor.top - height - 4 : 8;
  return { left: Math.max(8, Math.min(anchor.left, viewportWidth - width - 8)),
    top: Math.max(8, Math.min(desiredTop, viewportHeight - height - 8)), width, height };
}
