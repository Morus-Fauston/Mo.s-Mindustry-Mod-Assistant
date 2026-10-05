import type { SpriteAction, SpriteActionPayload, SpriteTarget, SpriteTargets } from './types';

interface Confirmation { action: 'import_sprite' | 'delete_sprite'; target: SpriteTarget }
interface ResourceSnapshot {
  identity: string;
  targets: SpriteTarget[];
  loading: boolean;
  pending: { action: SpriteAction; suffix: string } | null;
  confirmation: Confirmation | null;
  error: string;
}

/** Owns request/confirmation lifetimes only. Resource truth and history stay in Python. */
export function createResourceController(load: () => Promise<SpriteTargets>,
  onAction: (action: SpriteAction, payload: SpriteActionPayload) => Promise<void>) {
  let snapshot: ResourceSnapshot = { identity: '', targets: [], loading: true, pending: null, confirmation: null, error: '' };
  let generation = 0;
  const subscribers = new Set<() => void>();
  function publish(update: Partial<ResourceSnapshot>) {
    snapshot = { ...snapshot, ...update }; subscribers.forEach(listener => listener());
  }
  const busy = () => snapshot.loading || snapshot.pending !== null;
  const message = (failure: unknown) => failure instanceof Error ? failure.message : '贴图操作未完成，请重试。';

  async function read(current: number) {
    publish({ loading: true, error: '' });
    try {
      const result = await load();
      if (current === generation) publish({ targets: result.targets, loading: false });
    } catch (failure) {
      if (current === generation) publish({ error: message(failure), loading: false });
    }
  }

  async function execute(action: SpriteAction, payload: SpriteActionPayload) {
    if (busy()) return;
    const current = generation;
    publish({ pending: { action, suffix: payload.suffix }, error: '' });
    try {
      await onAction(action, payload);
      if (current !== generation) return;
      publish({ confirmation: null });
      // Cancellation and completion have the same void return contract.
      // Always read the real target state; never optimistically mark success.
      await read(current);
    } catch (failure) {
      if (current === generation) publish({ error: message(failure) });
    } finally {
      if (current === generation) publish({ pending: null });
    }
  }

  return {
    getSnapshot: () => snapshot,
    subscribe(listener: () => void) { subscribers.add(listener); return () => { subscribers.delete(listener); }; },
    async start(identity: string) {
      const current = ++generation;
      publish({ identity, targets: [], loading: true, pending: null, confirmation: null, error: '' });
      await read(current);
    },
    stop() { generation++; },
    async refresh() {
      if (busy()) return;
      publish({ confirmation: null });
      await read(++generation);
    },
    cancelConfirmation() { if (!busy()) publish({ confirmation: null }); },
    async request(action: SpriteAction, suffix: string) {
      if (busy()) return;
      const target = snapshot.targets.find(item => item.suffix === suffix);
      if (!target || (!target.exists && action !== 'import_sprite')) return;
      if (target.exists && (action === 'import_sprite' || action === 'delete_sprite')) {
        publish({ confirmation: { action, target }, error: '' });
      } else await execute(action, { suffix });
    },
    async confirm() {
      if (busy() || !snapshot.confirmation) return;
      const { action, target } = snapshot.confirmation;
      await execute(action, { suffix: target.suffix, ...(action === 'import_sprite' ? { overwrite: true } : { confirmed: true }) });
    },
  };
}
