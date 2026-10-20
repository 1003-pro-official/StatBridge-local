/** Leave native text undo and shortcuts outside this workspace untouched. */
export function workspaceHistoryAction(event: KeyboardEvent, root: HTMLElement): 'undo' | 'redo' | null {
  if (event.defaultPrevented || event.repeat || event.isComposing || !event.ctrlKey || event.altKey || event.metaKey) return null;
  const target = event.target;
  if (!(target instanceof Element)) return null;
  if (target.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"],[role="dialog"],[role="alertdialog"],dialog')) return null;
  if (!root.contains(target) && target !== root.ownerDocument.body) return null;
  if (root.ownerDocument.querySelector('[aria-modal="true"],dialog[open]')) return null;
  const key = event.key.toLowerCase();
  return key === 'z' && !event.shiftKey ? 'undo' : key === 'y' && !event.shiftKey ? 'redo' : null;
}
