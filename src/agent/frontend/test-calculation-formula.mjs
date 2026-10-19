import test from 'node:test';
import assert from 'node:assert/strict';
import {calculationFormula} from './src/calculationFormula.ts';
const labels={x:'생산자물가지수',cost:'회사 비용',a:'계산 1 결과'};
for(const [operator,expected] of [
 ['add','생산자물가지수 ＋ 회사 비용'],['subtract','생산자물가지수 − 회사 비용'],
 ['multiply','생산자물가지수 × 회사 비용'],['divide','생산자물가지수 ÷ 회사 비용'],
 ['inverse','1 ÷ 생산자물가지수'],['log','ln(생산자물가지수) (자연로그)'],
 ['yoy_pct','(생산자물가지수(당기) ÷ 생산자물가지수(전년 동일 시점) − 1) × 100 (%)'],
 ['pct_change','(생산자물가지수(당기) ÷ 생산자물가지수(2기간 전) − 1) × 100 (%)'],
 ['difference','생산자물가지수(당기) − 생산자물가지수(2기간 전)'],
 ['rebase_100','생산자물가지수(당기) ÷ 생산자물가지수(202001) × 100'],
 ['power','(생산자물가지수) ^ 2'],
 ['rolling_mean','생산자물가지수의 당기 포함 3기간 산술평균 (결측이면 계산하지 않음)'],
 ['cumulative_sum','생산자물가지수의 표시 시작기간부터 당기까지 누적합'],
 ['lag','생산자물가지수의 2기간 전 값'],
 ['period_change','(시작값 ÷ 종료값 − 1) × 100 (%)'],
])test(operator,()=>assert.equal(calculationFormula({operator,inputs:['x','cost'],lag:2,window:3,base_period:'202001',exponent:2,direction:'inverse'},labels),expected));
test('nested inputs reference earlier calculated result',()=>assert.equal(calculationFormula({operator:'divide',inputs:['a','x']},labels),'계산 1 결과 ÷ 생산자물가지수'));
