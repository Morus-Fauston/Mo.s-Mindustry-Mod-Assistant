import { useId, useLayoutEffect, useRef, useState } from 'react';
import { Compartment, EditorState, Prec, type Extension } from '@codemirror/state';
import { EditorView, drawSelection, highlightActiveLine, highlightActiveLineGutter, keymap, lineNumbers } from '@codemirror/view';
import { defaultKeymap } from '@codemirror/commands';
import { bracketMatching, HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { openSearchPanel, search, searchKeymap } from '@codemirror/search';
import { tags } from '@lezer/highlight';
import { createSourceInput } from './input';
import { forwardSourceChanges, sourceEcho, sourceLanguage } from './editor';
import { createSourceLocator, type SourceFocusRequest } from './location';
import styles from './SourceEditor.module.css';

export { SOURCE_DRAFT_FIELD } from './input';

export interface SourceEditorProps {
  identity: string;
  text: string;
  error: string;
  disabled: boolean;
  focusRequest?: SourceFocusRequest;
  onDraft(text: string): void;
  onCommit(): Promise<void>;
  onComposition(active: boolean): void;
  onFormat(): Promise<void>;
  onAction(action: 'save_opened' | 'undo' | 'redo'): void;
}

interface Instance {
  identity: string;
  props: SourceEditorProps;
  input: ReturnType<typeof createSourceInput>;
  view: EditorView;
  status: Compartment;
  reveal: ReturnType<typeof createSourceLocator>;
}

const highlight = HighlightStyle.define([
  { tag: tags.propertyName, class: styles.property },
  { tag: tags.string, class: styles.string },
  { tag: tags.number, class: styles.number },
  { tag: [tags.bool, tags.null], class: styles.literal },
  { tag: [tags.brace, tags.squareBracket, tags.separator], class: styles.punctuation },
]);

function statusExtensions(props: SourceEditorProps, errorId: string): Extension {
  return [EditorState.readOnly.of(props.disabled), EditorView.editable.of(!props.disabled),
    EditorView.contentAttributes.of({ 'aria-label': 'JSON 源码编辑区', 'aria-hidden': 'true',
      'aria-invalid': String(Boolean(props.error)), 'aria-describedby': props.error ? errorId : '',
      'aria-readonly': String(props.disabled), spellcheck: 'false' })];
}

/** CodeMirror owns presentation only; drafts and every undoable edit remain in the session. */
export function SourceEditor(props: SourceEditorProps) {
  const mount = useRef<HTMLDivElement>(null);
  const accessibilityInput = useRef<HTMLTextAreaElement>(null);
  const current = useRef<Instance | null>(null);
  const [composing, setComposing] = useState(false);
  const errorId = useId();
  const syncAccessibilityInput = (text: string) => {
    const input = accessibilityInput.current;
    if (input && input.value !== text) input.value = text;
  };

  useLayoutEffect(() => {
    if (!mount.current) return;
    // Each lifetime keeps its own callbacks, including cleanup of the old path's IME flag.
    const instance = { identity: props.identity, props, status: new Compartment(), reveal: createSourceLocator() } as Instance;
    instance.input = createSourceInput({
      onDraft: text => instance.props.onDraft(text),
      onCommit: () => instance.props.onCommit(),
      onComposition: active => instance.props.onComposition(active),
    });
    instance.input.setEnabled(!props.disabled);
    const action = (name: 'save_opened' | 'undo' | 'redo') => (view: EditorView) => {
      if (!view.composing && !instance.props.disabled) {
        instance.input.cancelScheduled(); instance.props.onAction(name);
      }
      return true;
    };
    instance.view = new EditorView({ parent: mount.current, state: EditorState.create({ doc: props.text, extensions: [
      sourceLanguage(), lineNumbers(), drawSelection(), highlightActiveLine(), highlightActiveLineGutter(),
      bracketMatching(), syntaxHighlighting(highlight), search({ top: true }),
      instance.status.of(statusExtensions(props, errorId)),
      Prec.highest(keymap.of([
        { key: 'Mod-s', run: action('save_opened'), stopPropagation: true, scope: 'editor search-panel' },
        { key: 'Mod-z', run: action('undo'), stopPropagation: true, scope: 'editor search-panel' },
        { key: 'Mod-Shift-z', run: action('redo'), stopPropagation: true, scope: 'editor search-panel' },
        { key: 'Mod-y', run: action('redo'), stopPropagation: true, scope: 'editor search-panel' },
      ])),
      // No history extension, history keymap or Tab trap.
      keymap.of([...searchKeymap, ...defaultKeymap]),
      EditorView.updateListener.of(update => forwardSourceChanges(update.transactions, text => {
        syncAccessibilityInput(text);
        instance.input.change(text);
      })),
      EditorView.domEventHandlers({
        compositionstart() { instance.input.composition(true); setComposing(true); },
        compositionend() { instance.input.composition(false); setComposing(false); },
        blur(event, view) {
          if (!(event.relatedTarget instanceof Node && view.dom.contains(event.relatedTarget))) {
            void instance.input.flush().catch(() => {});
          }
        },
      }),
    ] }) });
    current.current = instance;
    syncAccessibilityInput(props.text);
    setComposing(false);
    return () => {
      instance.input.dispose(); instance.view.destroy();
      if (current.current === instance) current.current = null;
    };
  }, [props.identity, errorId]);

  useLayoutEffect(() => {
    const instance = current.current;
    if (!instance || instance.identity !== props.identity) return;
    const previous = instance.props;
    instance.props = props;
    instance.input.setEnabled(!props.disabled);
    if (props.error) instance.input.cancelScheduled();
    if (previous.disabled !== props.disabled || previous.error !== props.error) {
      instance.view.dispatch({ effects: instance.status.reconfigure(statusExtensions(props, errorId)) });
    }
    const text = instance.view.state.doc.toString();
    if (text !== props.text) instance.view.dispatch(sourceEcho(text, props.text));
    syncAccessibilityInput(props.text);
    instance.reveal(instance.view, props.focusRequest, props.disabled);
  }, [props, errorId, composing]);

  return <section className={styles.source} aria-label="源码编辑" data-disabled={props.disabled}>
    <div className={styles.toolbar}>
      <span className={styles.title}>JSON 源码</span>
      <span className={styles.hint} role="status">{composing ? '中文输入中' : '与表单共用撤销记录'}</span>
      <button type="button" onClick={() => { if (current.current) openSearchPanel(current.current.view); }}>查找与替换</button>
      <button type="button" disabled={props.disabled || composing} onClick={() => {
        current.current?.input.cancelScheduled(); void props.onFormat().catch(() => {});
      }}>格式化</button>
    </div>
    {props.error && <p className={styles.error} id={errorId} role="alert">{props.error}</p>}
    <div className={styles.editor}>
      <div ref={mount} className={styles.cmMount} />
      <textarea
        className={styles.accessibilityInput}
        aria-label="JSON 源码"
        aria-invalid={Boolean(props.error)}
        aria-describedby={props.error ? errorId : undefined}
        aria-readonly={props.disabled}
        defaultValue={props.text}
        disabled={false}
        readOnly={props.disabled}
        tabIndex={-1}
        spellCheck={false}
        onChange={event => {
          const instance = current.current;
          if (!instance || instance.props.disabled) return;
          const next = event.currentTarget.value;
          const previous = instance.view.state.doc.toString();
          if (next === previous) return;
          instance.view.dispatch({ changes: { from: 0, to: instance.view.state.doc.length, insert: next } });
        }}
      />
    </div>
  </section>;
}
