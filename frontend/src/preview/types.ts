/** Scene coordinates already include the core's PPU=4 and Y-axis conversion. */
export interface PreviewLayer {
  key: string;
  resourceId: string;
  x: number;
  y: number;
  z: number;
  width: number;
  height: number;
  flipX: boolean;
  tooltip: string;
}

export interface PreviewCircle {
  key: string;
  cx: number;
  cy: number;
  radius: number;
  z: number;
  color: string;
  tooltip: string;
}

export interface PreviewScene {
  sessionId: string;
  width: number;
  height: number;
  layers: PreviewLayer[];
  circles: PreviewCircle[];
  warnings: string[];
  status: 'ready' | 'empty' | 'missing';
}

export interface PreviewResource {
  sessionId: string;
  resourceId: string;
  mime: 'image/png';
  dataUrl: string;
  width: number;
  height: number;
}
