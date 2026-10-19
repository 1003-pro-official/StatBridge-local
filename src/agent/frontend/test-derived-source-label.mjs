import test from 'node:test';
import assert from 'node:assert/strict';
import {resultSourceLabel} from './src/resultPresentation.ts';
test('file-only daily data never claims API data',()=>assert.equal(resultSourceLabel({derivedEvidence:{sourceSelections:Array.from({length:12},()=>({origin:'user_file'}))}}),'사용자 제공 파일'));
test('mixed inputs retain both source kinds',()=>assert.equal(resultSourceLabel({derivedEvidence:{sourceSelections:[{origin:'user_file'},{origin:'kosis_api'}]}}),'API·사용자 제공 파일'));
test('API-only and ordinary query retain KOSIS label',()=>{assert.equal(resultSourceLabel({derivedEvidence:{sourceSelections:[{origin:'kosis_api'}]}}),'한국은행 · KOSIS');assert.equal(resultSourceLabel({}),'한국은행 · KOSIS');});
