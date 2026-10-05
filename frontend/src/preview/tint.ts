import { colorizeRgba } from '../dynamic_preview/colorize';

interface Entry { pixels: ImageData; canvas: HTMLCanvasElement; color: string }

/** One current tint per decoded source, with the same total pixel ceiling as decoding. */
export function createTintCache() {
  const entries = new Map<HTMLImageElement, Entry>();
  let pixels = 0;
  return {
    image(source: HTMLImageElement, color: string): HTMLCanvasElement {
      let entry = entries.get(source);
      if (!entry) {
        const cost = source.naturalWidth * source.naturalHeight;
        if (!cost || pixels + cost > 16 * 1024 * 1024) throw new Error('动态染色总像素超过限制，已显示原贴图。');
        const canvas = document.createElement('canvas');
        canvas.width = source.naturalWidth; canvas.height = source.naturalHeight;
        const context = canvas.getContext('2d', { willReadFrequently: true });
        if (!context) throw new Error('动态染色不可用，已显示原贴图。');
        context.drawImage(source, 0, 0);
        entry = { canvas, pixels: context.getImageData(0, 0, canvas.width, canvas.height), color: '' };
        entries.set(source, entry); pixels += cost;
      }
      if (entry.color !== color) {
        const context = entry.canvas.getContext('2d')!;
        const output = context.createImageData(entry.canvas.width, entry.canvas.height);
        output.data.set(colorizeRgba(entry.pixels.data, color));
        context.putImageData(output, 0, 0); entry.color = color;
      }
      return entry.canvas;
    },
    clear() {
      for (const entry of entries.values()) { entry.canvas.width = 0; entry.canvas.height = 0; }
      entries.clear(); pixels = 0;
    },
  };
}
