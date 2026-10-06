import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const read=name=>readFileSync(new URL(name,import.meta.url),'utf8');
const chat=read('./src/Sujeongi.tsx');
const editor=read('./src/ChartSketchEditor.tsx');

test('character chat reuses the existing validated visual edit contract',()=>{
  assert.match(editor,/<Sujeongi[^>]+onEdit=\{apply\}/);
  assert.match(editor,/onEdit\(\{instruction:requestedInstruction\.trim\(\),visual\}\)/);
  assert.ok(!chat.includes('series_label')&&!chat.includes('Math.round(x'));
  assert.match(editor,/resolveMarkSelection/);
  assert.match(editor,/moveMark/);
  assert.match(editor,/resizeMark/);
});
test('success feedback requires success; failures preserve the draft',()=>{
  assert.match(chat,/if\(success\)\{setDraft\(""\)/);
  assert.match(chat,/if\(!instruction\|\|loading\|\|inFlight\.current\)return/);
  assert.match(chat,/slice\(-40\)/);
  assert.match(chat,/currentSession\.current!==startedSession/);
});
test('all four drawing tools and session reset remain available',()=>{
  for(const tool of ['rectangle','pen','arrow','text'])assert.ok(chat.includes('"'+tool+'"'));
  assert.match(chat,/setDraft\(""\);setMessages\(\[\]\);setOpen\(false\)/);
  assert.match(editor,/action:"undo"/);
  assert.match(editor,/action:"redo"/);
});
