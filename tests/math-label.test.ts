import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mathParts} from '../src/math-label';
test('上下标解析保留普通文本且不解释 HTML',()=>{
  assert.deepEqual(mathParts('x_{max}^{2}'),[{text:'x',kind:'plain'},{text:'max',kind:'sub'},{text:'2',kind:'sup'}]);
  assert.deepEqual(mathParts('v_1'),[{text:'v',kind:'plain'},{text:'1',kind:'sub'}]);
  assert.deepEqual(mathParts('<img>'),[{text:'<img>',kind:'plain'}]);
});
