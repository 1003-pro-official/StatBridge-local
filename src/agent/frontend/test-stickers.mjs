import test from 'node:test';
import assert from 'node:assert/strict';
import {stickerCenter,moveSticker,rotationAt} from './src/stickerTransform.ts';

const box={left:50,top:100,width:800,height:400};
const sticker={id:'arrow',asset_id:'sticker-5-03',x:.25,y:.75,size:.3,angle:45,opacity:.8};
test('paper coordinates map from bottom-up y to screen coordinates',()=>{
  assert.deepEqual(stickerCenter(sticker,box),{x:250,y:200});
});
test('drag preserves appearance, uses both plot dimensions and does not mutate state',()=>{
  const copy=structuredClone(sticker),next=moveSticker(sticker,80,-40,box);
  assert.equal(next.x,.35);assert.equal(next.y,.85);
  assert.equal(next.angle,45);assert.equal(next.size,.3);assert.equal(next.opacity,.8);
  assert.deepEqual(sticker,copy);
  assert.deepEqual(stickerCenter(next,box),{x:330,y:160});
});
test('drag stays within plot anchor boundaries',()=>{
  assert.equal(moveSticker(sticker,-5000,5000,box).x,0);
  assert.equal(moveSticker(sticker,-5000,5000,box).y,0);
  assert.equal(moveSticker(sticker,5000,-5000,box).x,1);
  assert.equal(moveSticker(sticker,5000,-5000,box).y,1);
});
test('rotation handle supports all directions',()=>{
  const center={x:100,y:100};
  assert.equal(rotationAt(100,0,center),0);
  assert.equal(rotationAt(200,100,center),90);
  assert.equal(rotationAt(100,200,center),180);
  assert.equal(rotationAt(0,100,center),270);
});
