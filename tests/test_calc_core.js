'use strict';

const assert = require('assert');
const path = require('path');
const {
  CalculatorEngine,
  evaluateExpression,
} = require(path.join(__dirname, '..', 'renderer', 'calc-core.js'));

function run(keys) {
  const engine = new CalculatorEngine();
  let historyEntry = null;
  keys.forEach(key => {
    const outcome = engine.press(key);
    if (outcome.historyEntry) historyEntry = outcome.historyEntry;
  });
  return { engine, historyEntry };
}

assert.strictEqual(evaluateExpression('2+3*4'), 14);
assert.strictEqual(evaluateExpression('(2+3)*4'), 20);
assert.strictEqual(evaluateExpression('2^3^2'), 512);
assert.strictEqual(evaluateExpression('-2^2'), -4);
assert.strictEqual(evaluateExpression('2^-2'), 0.25);
assert.strictEqual(evaluateExpression('1e3+2'), 1002);
assert.strictEqual(evaluateExpression('sin(30)+2'), 2.5);
assert.strictEqual(evaluateExpression('sin⁻¹(0.5)'), 30.000000000000004);
assert.strictEqual(evaluateExpression('√(9)+fact(4)'), 27);
assert.strictEqual(evaluateExpression('10^(2)+e^(0)'), 101);
assert.strictEqual(evaluateExpression('200+10%'), 220);
assert.strictEqual(evaluateExpression('−(2+3)'), -5);

assert.strictEqual(run(['2', '+', '3', '=']).engine.result, '5');
assert.strictEqual(run(['2', '+', '3', '*', '4', '=']).engine.result, '14');
assert.strictEqual(run(['(', '2', '+', '3', ')', '*', '4', '=']).engine.result, '20');
assert.strictEqual(run(['2', '+', '-', '3', '=']).engine.result, '-1');
assert.strictEqual(run(['1', 'EXP', '3', '+', '2', '=']).engine.result, '1002');

assert.strictEqual(run(['3', '0', 'sin', '=']).engine.result, '0.5');
assert.strictEqual(run(['3', '0', 'sin', '+', '2', '=']).engine.result, '2.5');
assert.strictEqual(run(['9', 'sqrt', '=']).engine.result, '3');
assert.strictEqual(run(['5', 'fact', '=']).engine.result, '120');
assert.strictEqual(run(['1', '7', '1', 'fact']).engine.result, 'Error');

assert.strictEqual(run(['2', '0', '0', '+', '1', '0', '%']).engine.result, '220');
assert.strictEqual(run(['2', '0', '0', '-', '1', '0', '%']).engine.result, '180');
assert.strictEqual(run(['2', '0', '0', '*', '1', '0', '%']).engine.result, '20');
assert.strictEqual(run(['5', '0', '%']).engine.result, '0.5');

assert.strictEqual(run(['1', '/', '0', '=']).engine.result, 'Error');
assert.strictEqual(run(['9', 'sqrt', '=']).historyEntry.expr, '√(9)');

const editable = new CalculatorEngine();
editable.loadExpression('12+34', '46');
assert.strictEqual(editable.snapshot().displayExpression, '12+34');
assert.strictEqual(editable.snapshot().result, '46');
editable.setExpression('12+3*4');
assert.strictEqual(editable.snapshot().result, '24');
assert.strictEqual(editable.press('=').historyEntry.expr, '12+3*4');

const historyUnary = new CalculatorEngine();
historyUnary.loadExpression('fact(9)', '362880');
assert.strictEqual(historyUnary.snapshot().result, '362880');
historyUnary.setExpression('fact(8)');
assert.strictEqual(historyUnary.snapshot().result, '40320');

console.log('calc-core: all tests passed');
