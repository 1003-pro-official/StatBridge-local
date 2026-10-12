// Match only standalone history requests; combined edits go to normal interpretation.
export function historyIntent(text:string):'undo'|'redo'|null {
 const value=text.trim().replace(/[.!?。]+$/,'');
 if(/^(?:방금|마지막|이전)(?:\s*(?:수정|작업)(?:한 것)?(?:만|을|을만)?)?\s*(?:취소|되돌려)(?:해줘|줘|해 주세요|주세요)?$/.test(value)||/^(?:되돌리기|undo)$/i.test(value))return 'undo';
 if(/^(?:다시 실행|다시 적용|취소한 수정 다시 적용)(?:해줘|해 주세요|해주세요|줘)?$/.test(value)||/^redo$/i.test(value))return 'redo';
 return null;
}
