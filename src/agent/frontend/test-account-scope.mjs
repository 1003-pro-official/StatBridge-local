import test from 'node:test';
import assert from 'node:assert/strict';
import {ownsHistory} from './src/accountScope.ts';
test('browser history restores only the current account',()=>{
 assert.equal(ownsHistory({account:'history.account.1'},'history.account.1'),true);
 assert.equal(ownsHistory({account:'history.account.1',result:{private:true}},'history.account.2'),false);
 assert.equal(ownsHistory({statbridge:true,result:{private:true}},'history.account.1'),false);
 assert.equal(ownsHistory(null,'history.account.1'),false);
});
