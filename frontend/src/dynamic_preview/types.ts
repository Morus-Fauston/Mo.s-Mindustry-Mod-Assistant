import type { PreviewLayer } from '../preview/types';
import type { AnimationState } from './math';

export interface DynamicResource { resourceId: string; width: number; height: number }
export interface DynamicPreviewDescriptor {
  supported: boolean;
  notices: string[];
  recoilTime: number;
  cooldownTime: number;
  teams: { value: string; label: string; color: string }[];
  healthLevels: { value: string; label: string; fraction: number }[];
  directions: { value: string; label: string; degrees: number }[];
  weapons: { nodeId: string; layerKeys: string[]; recoilDistance: number; recoilPower: number; flashCenter: { x: number; y: number } }[];
  engine: null | { nodeId: string; outerIndex: number; innerIndex: number; size: number };
  teamLayerKeys: string[];
  cellLayerKeys: string[];
  heat: null | PreviewLayer & { color: string; nodeId: string };
  treads: null | { nodeId: string; layerKey: string; frames: DynamicResource[] };
  flash: { radius: number; color: string; z: number };
  colorize: 'qt-colorize-strength-1';
}

export interface DynamicPreviewState {
  readonly enabled: boolean;
  readonly paused: boolean;
  readonly speed: 0.5 | 1 | 2;
  readonly moving: boolean;
  readonly direction: string;
  readonly team: string;
  readonly health: string;
  readonly animation: AnimationState;
}
export type DynamicAction = { type: 'start' | 'stop' | 'togglePause' | 'step' | 'fire' | 'reset' }
  | { type: 'speed'; value: 0.5 | 1 | 2 }
  | { type: 'moving'; value: boolean }
  | { type: 'direction' | 'team' | 'health'; value: string };
