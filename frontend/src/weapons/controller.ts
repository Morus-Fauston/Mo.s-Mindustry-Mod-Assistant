import type { BasicFormProps } from '../forms/BasicForm';

interface Snapshot { identity: string; pending: boolean; error: string }

/** Request state only; array data and undo belong to the Python command stack. */
export function createWeaponController() {
  let snapshot: Snapshot = { identity: '', pending: false, error: '' };
  let generation = 0, active = false;
  let action: BasicFormProps['onAction'];
  const listeners = new Set<() => void>();
  const publish = (next: Partial<Snapshot>) => { snapshot = { ...snapshot, ...next }; listeners.forEach(listener => listener()); };
  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
    start(identity: string, callback: BasicFormProps['onAction']) {
      generation++; active = true; action = callback; publish({ identity, pending: false, error: '' });
    },
    stop() { active = false; generation++; },
    async run(name: string, payload: Record<string, unknown>): Promise<boolean> {
      if (!active || snapshot.pending) return false;
      const token = generation;
      publish({ pending: true, error: '' });
      try {
        await action(name, payload);
        return active && token === generation;
      } catch (failure) {
        if (active && token === generation) publish({ error: failure instanceof Error ? failure.message : '武器修改未能完成，请重试。' });
        return false;
      } finally { if (active && token === generation) publish({ pending: false }); }
    },
  };
}
