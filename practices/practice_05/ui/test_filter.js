function assert(name, cond) {
  const el = document.getElementById('test-output');
  const line = document.createElement('div');
  line.textContent = (cond ? 'PASS: ' : 'FAIL: ') + name;
  line.style.color = cond ? 'green' : 'red';
  el.appendChild(line);
  if (!cond) console.error('FAIL', name);
}

const items = [{id:'1',name:'Alpha'},{id:'2',name:'Beta'},{id:'3',name:'Gamma'}];

function runTests() {
  assert('happy_path alp -> Alpha', filterItems('alp', items).length === 1 && filterItems('alp', items)[0].name === 'Alpha');
  assert('case-insensitive GA -> Gamma', filterItems('GA', items).length === 1 && filterItems('GA', items)[0].name === 'Gamma');
  assert('boundary_empty zzz -> []', filterItems('zzz', items).length === 0);
  assert('reset empty query returns full', filterItems('', items).length === items.length);
  let threw = false;
  try { filterItems('@@@', items); } catch(e) { threw = (e.code === 'ValidationError.INVALID_FILTER' || String(e).includes('INVALID_FILTER')); }
  assert('validation_error @@@ throws', threw === true);
}
window.addEventListener('DOMContentLoaded', runTests);
