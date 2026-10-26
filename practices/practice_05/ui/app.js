/* eslint-disable no-undef */
const rxValid = /^[a-zA-Z0-9\s]{0,40}$/;

// Чистая функция фильтрации по контракту: бросает INVALID_FILTER при недопустимом вводе,
// при пустом запросе возвращает исходный список, иначе — подстрочная фильтрация без учёта регистра
function filterItems(query, items) {
  const rxLocal = /^[a-zA-Z0-9\s]{0,40}$/;
  const q = (query || '').toString();
  if (q === '') return items;
  if (!rxLocal.test(q)) {
    const err = new Error('ValidationError.INVALID_FILTER');
    err.code = 'ValidationError.INVALID_FILTER';
    throw err;
  }
  const lower = q.toLowerCase();
  return (items || []).filter(it => String(it.name || '').toLowerCase().includes(lower));
}
let allItems = [];

const $filter = document.getElementById('filter');
const $reset = document.getElementById('reset');
const $list = document.getElementById('list');
const $error = document.getElementById('error');
const $empty = document.getElementById('empty');

fetch('items.json', { cache: 'no-store' })
  .then(r => r.json())
  .then(items => {
    allItems = items;
    render(items);
  });

function setError(msg) {
  if (msg) {
    $error.textContent = msg;
    $error.hidden = false;
  } else {
    $error.hidden = true;
    $error.textContent = '';
  }
}

function render(items) {
  $list.innerHTML = '';
  if (!items.length) {
    $empty.hidden = false;
    return;
  }
  $empty.hidden = true;
  for (const it of items) {
    const li = document.createElement('li');
    li.textContent = it.name;
    $list.appendChild(li);
  }
}

function applyFilter(q) {
  try {
    setError('');
    const filtered = filterItems(q, allItems);
    render(filtered);
  } catch (e) {
    if (e && (e.code === 'ValidationError.INVALID_FILTER' || String(e.message || e).includes('INVALID_FILTER'))) {
      setError('Недопустимый фильтр. Используйте буквы, цифры и пробел, до 40 символов.');
      render(allItems);
    } else {
      setError('Неизвестная ошибка фильтрации');
      render(allItems);
    }
  }
}

$filter.addEventListener('input', (e) => {
  applyFilter(e.target.value);
});

$reset.addEventListener('click', () => {
  $filter.value = '';
  applyFilter('');
});
