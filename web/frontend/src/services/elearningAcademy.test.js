import { expect, it } from 'vitest';
import { academyReturnPath } from './elearningAcademy';
it.each(['https://foreign.example','//foreign.example','/academy/other/form','/academy/testing/../other','/academy/testing/%00form','/academy/testing/%2500form','/academy/testing/%5cform'])('rejects unsafe Academy return %s', target => {
 expect(academyReturnPath(target,'/academy/testing','https://madar.example',true)).toBe('/academy/testing');
});
it.each(['/academy/testing/about/our-story?campaign=1#form','/my-learning/affiliate','/my-learning/exchange/own'])('retains contextual authorized returns %s', target=>{
 expect(academyReturnPath(target,'/academy/testing','https://madar.example',true)).toBe(target);
});
