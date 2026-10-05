export interface SpriteTarget { suffix: string; label: string; path: string; exists: boolean }
export interface SpriteTargets { targets: SpriteTarget[] }
export type SpriteAction = 'import_sprite' | 'delete_sprite' | 'reveal_sprite';
export interface SpriteActionPayload { suffix: string; overwrite?: boolean; confirmed?: boolean }
