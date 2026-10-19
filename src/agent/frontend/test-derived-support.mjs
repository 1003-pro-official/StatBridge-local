import test from 'node:test';
import assert from 'node:assert/strict';
import {apiSupportScope,canConnectMissingFiles} from './src/derivedAvailability.ts';
for(const [statuses,scope,upload] of [
 [['available'],'api_only',false], [['available','not_found'],'mixed',true],
 [['not_found'],'unsupported',false],[['not_found','not_found'],'unsupported',false],
 [['api_error','not_found'],'verification_pending',false],
 [['selection_required'],'verification_pending',false],
 [['available','api_error'],'mixed',false],[['available','not_found','api_error'],'mixed',false],
])test(statuses.join(' + '),()=>{const data={status:'checked',sources:statuses.map(status=>({status}))};assert.equal(apiSupportScope(data),scope);assert.equal(canConnectMissingFiles(data),upload);});
test('metadata scan in progress cannot open upload',()=>assert.equal(canConnectMissingFiles({status:'verifying',sources:[]}),false));
