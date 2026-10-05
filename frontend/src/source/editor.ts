import { Annotation, EditorState, Transaction, type Extension, type TransactionSpec } from '@codemirror/state';
import { json } from '@codemirror/lang-json';

const backendEcho = Annotation.define<boolean>();

/** Translate all visible and screen-reader phrases used by the installed search package. */
export const sourcePhrases: Record<string, string> = {
  Find: '查找', Replace: '替换', next: '下一处', previous: '上一处', all: '选中全部',
  'match case': '区分大小写', regexp: '正则表达式', 'by word': '完整词语',
  replace: '替换', 'replace all': '全部替换', close: '关闭',
  'current match': '当前匹配', 'on line': '所在行', 'Go to line': '跳转到行', go: '跳转',
  'replaced match on line $': '已替换第 $ 行的匹配', 'replaced $ matches': '已替换 $ 处匹配',
  'Control character': '控制字符',
};

export function sourceLanguage(): Extension {
  return [json(), EditorState.phrases.of(sourcePhrases), EditorState.tabSize.of(2)];
}

/** Preserve unchanged ranges (and their cursor positions); never parse JSON in JS. */
export function sourceEcho(previous: string, next: string): TransactionSpec {
  let from = 0, oldEnd = previous.length, newEnd = next.length;
  while (from < oldEnd && from < newEnd && previous[from] === next[from]) from++;
  while (oldEnd > from && newEnd > from && previous[oldEnd - 1] === next[newEnd - 1]) { oldEnd--; newEnd--; }
  return { changes: { from, to: oldEnd, insert: next.slice(from, newEnd) },
    annotations: [backendEcho.of(true), Transaction.addToHistory.of(false)] };
}

export function forwardSourceChanges(transactions: readonly Transaction[], onDraft: (text: string) => void): void {
  const changed = transactions.filter(transaction => transaction.docChanged && !transaction.annotation(backendEcho));
  if (changed.length) onDraft(changed[changed.length - 1].state.doc.toString());
}
