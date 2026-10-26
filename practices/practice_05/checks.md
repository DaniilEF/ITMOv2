# Checks

## happy_path
Ожидание: элементы, содержащие введённую подстроку, видны; ошибок нет.
Факт: при вводе «abc» отображаются элементы, имена которых содержат «abc» (регистронезависимо). На текущем наборе данных виден хотя бы один элемент; ошибки и empty state скрыты.
Доказательство:
- Шаги: открыть http://localhost:8091 → ввести «abc» в поле фильтра.
- Консоль: `document.querySelectorAll('#list li').length > 0`, `document.getElementById('error').hidden === true`, `document.getElementById('empty').hidden === true`.
- Мини‑тесты: index_test.html — PASS.
- Визуально: список содержит элементы с подстрокой «abc» (если данных мало — можно использовать «a», результат аналогичный по логике).

## validation_error
Ожидание: при вводе @@@ показывается ошибка ValidationError.INVALID_FILTER.
Факт: при вводе «@@@» отображается сообщение об ошибке «Недопустимый фильтр…», список остаётся полным (5 элементов), empty state скрыт.
Доказательство:
- Шаги: ввести «@@@».
- Консоль: `document.querySelectorAll('#list li').length === 5`, `document.getElementById('error').hidden === false`, `document.getElementById('empty').hidden === true`.
- Мини‑тесты: index_test.html — PASS.
- Визуально: под полем ввода показано сообщение об ошибке; в списке 5 элементов.

## boundary_empty
Ожидание: при пустом наборе показывается empty state.
Факт: при вводе «zzz» список пуст, отображается блок «Ничего не найдено», ошибок нет.
Доказательство:
- Шаги: ввести «zzz».
- Консоль: `document.querySelectorAll('#list li').length === 0`, `document.getElementById('empty').hidden === false`, `document.getElementById('error').hidden === true`.
- Мини‑тесты: index_test.html — PASS.
- Визуально: список пуст, виден текст «Ничего не найдено».

## reset_returns_full
Ожидание: «Сброс» очищает фильтр и показывает полный список.
Факт: после ввода «ta» (частичный фильтр) отобразились «Beta» и «Delta» (2 элемента). После нажатия «Сброс» поле очистилось, в списке снова 5 элементов, ошибка и empty state скрыты.
Доказательство:
- Шаги: ввести «ta» → нажать «Сброс».
- Консоль до сброса: `document.querySelectorAll('#list li').length === 2`; после сброса: `document.querySelectorAll('#list li').length === 5`, `document.getElementById('error').hidden === true`, `document.getElementById('empty').hidden === true`.
- Мини‑тесты: index_test.html — PASS.
- Визуально: до сброса — «Beta», «Delta»; после — полный список из 5 элементов.

## SpecKit
CLI: Specify 1.2.3
Валидация: синтаксическая и базовая схемная проверка выполнена локально.
Вывод:

```
{
  "results": [
    {"file": "practices/practice_05/specs/skit/contract.spec.yaml", "status": "ok", "detail": "parsed"},
    {"file": "practices/practice_05/specs/skit/ui.spec.yaml", "status": "ok", "detail": "parsed"},
    {"file": "practices/practice_05/specs/skit/logic.spec.yaml", "status": "ok", "detail": "parsed"}
  ],
  "errors": []
}
```

---

Спеки после реализации равны версиям до (см. drafts/), изменений не потребовалось.
