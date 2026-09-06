import {test} from 'node:test';
import assert from 'node:assert/strict';
import {isSameOrigin,validBackendPath,validateIdentity} from '../lib/security';
test('write requests require exact configured origin',()=>{
 assert.equal(isSameOrigin('https://ocr.example','https://ocr.example'),true);
 assert.equal(isSameOrigin('https://evil.example','https://ocr.example'),false);
 assert.equal(isSameOrigin(null,'https://ocr.example'),false);
});
test('backend paths reject traversal and encoded path separators',()=>{
 assert.equal(validBackendPath(['jobs','abc','artifacts','pdf']),true);
 for(const p of [['..'],['%2e%2e'],['a/b'],['a\\b'],['%252f']]) assert.equal(validBackendPath(p),false);
});
test('identity must contain a matching selected membership',()=>{
 const profile={user_id:'u1',tenant_id:'t1',role:'member',teams:[{id:'t1',name:'Team',role:'member'}]};
 assert.deepEqual(validateIdentity(profile),profile);
 assert.throws(()=>validateIdentity({...profile,tenant_id:'t2'}));
 assert.throws(()=>validateIdentity({...profile,role:'owner'}));
});
