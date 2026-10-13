import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const read=name=>readFileSync(new URL(name,import.meta.url),'utf8');
const chat=read('./src/Sujeongi.tsx');
const editor=read('./src/ChartSketchEditor.tsx');

test('character chat reuses the existing validated visual edit contract',()=>{
  assert.match(editor,/<Sujeongi[\s\S]*?onEdit=\{apply\}/);
  assert.match(editor,/onEdit\(\{instruction:requestedInstruction\.trim\(\)[\s\S]*?visual,conversation,reference_files:references/);
  assert.ok(!chat.includes('series_label')&&!chat.includes('Math.round(x'));
  assert.match(editor,/resolveMarkSelection/);
  assert.match(editor,/moveMark/);
  assert.match(editor,/resizeMark/);
});
test('success feedback requires success; failures preserve the draft',()=>{
  assert.match(chat,/if\(success\)\{setDraft\(""\)/);
  assert.match(chat,/if\(\(!instruction&&!canSubmitMarks&&!references\.length\)\|\|loading\|\|inFlight\.current\)return/);
  assert.match(chat,/savedConversation\(sessionId\)/);
  assert.match(chat,/currentSession\.current!==startedSession/);
});
test('all four drawing tools and session reset remain available',()=>{
  for(const tool of ['rectangle','pen','arrow','text'])assert.ok(editor.includes('"'+tool+'"'));
  assert.match(chat,/setDraft\(""\);setReferences\(\[\]\);[\s\S]*?setConversation\(\{sessionId,messages:savedConversation\(sessionId\)\}\);setOpen\(false\)/);
  assert.match(editor,/historyAction\(["\x27]undo["\x27]\)/);
  assert.match(editor,/historyAction\(["\x27]redo["\x27]\)/);
});
