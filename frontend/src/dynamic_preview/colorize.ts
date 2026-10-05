/** Equivalent to Qt 6.11.1 QGraphicsColorizeEffect strength=1 in premultiplied ARGB.
 * Reference: qtbase/src/widgets/effects/qpixmapfilter.cpp grayscale + Screen composition.
 * Source and result use Canvas ImageData's straight RGBA. White stays white, alpha is preserved.
 */
export function colorizeRgba(source: Uint8ClampedArray, tintHex: string): Uint8ClampedArray {
  if (source.length % 4 !== 0 || !/^#[0-9a-f]{6}$/i.test(tintHex)) throw new Error('预览染色数据无效。');
  const tint = [1, 3, 5].map(offset => parseInt(tintHex.slice(offset, offset + 2), 16));
  const output = new Uint8ClampedArray(source.length);
  const div255 = (value: number) => (value + (value >> 8) + 128) >> 8;
  for (let index = 0; index < source.length; index += 4) {
    const alpha = source[index + 3];
    output[index + 3] = alpha;
    if (!alpha) continue;
    const red = div255(source[index] * alpha), green = div255(source[index + 1] * alpha), blue = div255(source[index + 2] * alpha);
    const gray = (11 * red + 16 * green + 5 * blue) >> 5;
    for (let channel = 0; channel < 3; channel++) {
      const screen = tint[channel] + gray - div255(tint[channel] * gray);
      const premultiplied = div255(screen * alpha);
      output[index + channel] = Math.floor(premultiplied * 255 / alpha + 0.5);
    }
  }
  return output;
}
