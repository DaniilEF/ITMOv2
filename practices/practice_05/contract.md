# Контракт фичи: Фильтр существующего списка

Цель: согласованный контракт между UI и логикой для фильтрации списка по строке с валидацией, пустым состоянием и сбросом.

## Модели

- Item
  - id: string
  - name: string
- ValidationError
  - code: enum [INVALID_FILTER]
  - message: string

## Ошибки

- ValidationError.INVALID_FILTER
  - message: «Недопустимый фильтр. Используйте буквы, цифры и пробел, до 40 символов.»
  - Условия возникновения: ввод не соответствует regex ^[a-zA-Z0-9\s]{0,40}$ (недопустимые символы или длина > 40).

## Состояния UI и триггеры

- loading
  - Резерв для асинхронных операций (в статическом UI не используется).
- ready
  - Триггеры: стартовое состояние; допустимый ввод с ≥1 совпадением; действие «Сброс».
  - Отображение: список элементов (полный или отфильтрованный), скрыты error_banner и empty_view.
- empty
  - Триггер: допустимый ввод, по результату фильтрации совпадений нет.
  - Отображение: скрыт список, показан empty_view «Ничего не найдено», скрыт error_banner.
- error
  - Триггер: недопустимый ввод (regex не пройден).
  - Отображение: показан error_banner с ValidationError.INVALID_FILTER; список остаётся полным.

## Действия UI

- type in filter_input value="<query>"
  - При пустом value: перейти в ready, показать полный список, ошибки нет.
  - При недопустимом value: перейти в error, показать сообщение об ошибке, показать полный список.
  - При допустимом value: вызвать фильтрацию; если результат пуст — перейти в empty, иначе остаться в ready.
- click reset_button
  - Очистить filter_input; перейти в ready; показать полный список; скрыть error_banner и empty_view.

## Операция логики

- filterItems(query: string, items: Item[]) -> items: Item[]
  - Правила:
    - Если query соответствует ^[a-zA-Z0-9\s]{0,40}$: вернуть элементы, где `item.name` содержит `query` как подстроку без учёта регистра (case-insensitive).
    - Иначе: бросить ValidationError.INVALID_FILTER.
  - Инварианты:
    - Пустой query возвращает исходный список `items` без ошибок.
    - Сравнение по подстроке нечувствительно к регистру.

## Соответствие сценариев UI ↔ логика

- happy_path
  - UI: type value="abc" → state: ready; виден список совпадающих элементов; error/empty скрыты.
  - Логика: filterItems("abc", items) → returns: подмножество, где `name` содержит "abc" (case-insensitive).
- validation_error
  - UI: type value="@@@" → state: error; показан error_banner ValidationError.INVALID_FILTER; в списке полный набор.
  - Логика: filterItems("@@@", items) → throws ValidationError.INVALID_FILTER.
- boundary_empty
  - UI: type value="zzz" (нет совпадений) → state: empty; показан empty_view; ошибок нет.
  - Логика: filterItems("zzz", items) → returns: [].
- reset_returns_full
  - UI: click reset_button → очистка поля; state: ready; показан полный список; скрыты error/empty.
  - Логика: filterItems("", items) → returns: исходный `items`.

## Проверяемые примеры

- Query="alp" → UI: один элемент «Alpha»; Логика: 1 совпадение.
- Query="GA" → UI: «Gamma»; Логика: регистронезависимость подтверждена.
- Query="@@@" → UI: ошибка; Логика: исключение INVALID_FILTER.
- Query="zzz" → UI: empty_view; Логика: [].
- Reset → UI: 5 элементов; Логика: возвращён исходный набор.

## Примечания реализации

- В статическом UI данные берутся из items.json, фильтрация выполняется на клиенте по тем же правилам.
- При переносе на серверный API контракт сохраняется без изменений: UI вызывает `GET /api/items?query=...` или аналог, сервер применяет правила `filterItems` и возвращает список либо код/сообщение ошибки для INVALID_FILTER.
