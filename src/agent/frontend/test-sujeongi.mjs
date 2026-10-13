import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const read=name=>readFileSync(new URL(name,import.meta.url),'utf8');
const chat=read('./src/Sujeongi.tsx');
const editor=read('./src/ChartSketchEditor.tsx');

test('character chat reuses the existing validated visual edit contract',()=>{
  assert.match(editor,/<Sujeongi[^>]+onEdit=\{apply\}/);
  assert.match(editor,/onEdit\(\{instruction:requestedInstruction\.trim\(\),visual,conversation,/);
  assert.ok(!chat.includes('series_label')&&!chat.includes('Math.round(x'));
  assert.match(editor,/resolveMarkSelection/);
  assert.match(editor,/moveMark/);
  assert.match(editor,/resizeMark/);
});
test('success feedback requires success; failures preserve the draft',()=>{
  assert.match(chat,/if\(success\)\{setDraft\(""\)/);
  assert.match(chat,/if\(\(!instruction&&!canSubmitMarks\)\|\|loading\|\|inFlight\.current\)return/);
  assert.match(chat,/sessionStorage\.setItem\(`statbridge\.sujeongi\.chat\.\$\{sessionId\}`,JSON\.stringify\(conversation\.messages\)\)/);
  assert.match(chat,/conversation\.sessionId===sessionId\?conversation\.messages:\[\]/);
  assert.match(chat,/currentSession\.current!==startedSession/);
});
test('drawing tools, history controls and per-session conversation remain available',()=>{
  for(const tool of ['rectangle','pen','arrow','text'])assert.ok(editor.includes('"'+tool+'"'));
  assert.match(chat,/setDraft\(""\);setPendingColors\(null\);setConversation\(\{sessionId,messages:savedConversation\(sessionId\)\}\);setOpen\(false\)/);
  assert.match(editor,/historyAction\("undo"\)/);
  assert.match(editor,/historyAction\("redo"\)/);
  assert.match(editor,/onEdit\(\{instruction:"",action\}\)/);
});
