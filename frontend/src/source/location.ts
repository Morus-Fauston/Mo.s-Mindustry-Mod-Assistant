import type { Text } from '@codemirror/state';
import type { EditorView } from '@codemirror/view';

export interface SourceFocusRequest { token: number; line: number; column: number }

/** Python JSON diagnostics count Unicode code points; CodeMirror counts UTF-16 units. */
export function sourceOffset(doc: Text, line: number, column: number): number | null {
  if (!Number.isSafeInteger(line) || !Number.isSafeInteger(column)) return null;
  const target = doc.line(Math.min(doc.lines, Math.max(1, line)));
  let offset = target.from;
  let remaining = Math.max(1, column) - 1;
  for (const character of target.text) {
    if (!remaining--) break;
    offset += character.length;
  }
  return offset;
}

/** App tokens increase monotonically; readiness never consumes a request. */
export function createSourceLocator() {
  let consumed: number | undefined;
  return (view: Pick<EditorView, 'state' | 'dom' | 'composing' | 'dispatch' | 'focus'>,
    request: SourceFocusRequest | undefined, disabled: boolean): boolean => {
    if (!request || !Number.isSafeInteger(request.token) || consumed !== undefined && request.token <= consumed || disabled || view.composing
        || !view.dom.getClientRects().length) return false;
    const visibility = view.dom.ownerDocument.defaultView?.getComputedStyle(view.dom).visibility;
    if (visibility === 'hidden' || visibility === 'collapse') return false;
    const anchor = sourceOffset(view.state.doc, request.line, request.column);
    if (anchor === null) return false;
    view.dispatch({ selection: { anchor }, scrollIntoView: true });
    view.focus();
    consumed = request.token;
    return true;
  };
}
