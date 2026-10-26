# Демо: Фильтр списка

Цель: запустить статический UI и проверить четыре сценария фичи «Фильтр существующего списка».

## Запуск

Вариант A: привязка к 0.0.0.0 (удобно открывать из браузера Windows к WSL2)

```bash
python3 -m http.server 8091 --bind 0.0.0.0 --directory practices/practice_05/ui
```

Открыть:
- Из WSL: http://localhost:8091
- Из Windows: http://<WSL_IP>:8091 (получить IP: `hostname -I`, взять первый адрес)

Вариант B: привязка к localhost

```bash
python3 -m http.server 8090 --bind 127.0.0.1 --directory practices/practice_05/ui
```

Открыть:
- http://localhost:8090

Примечания:
- IP WSL может меняться после перезапуска; если используете bind 0.0.0.0, заново выполните `hostname -I`.
- Остановить сервер: Ctrl+C в терминале или `pkill -f "http.server 8091"`.

## Проверка сценариев

1. happy_path
- Введите «alp». Ожидается один элемент: Alpha. Ошибок нет, empty state скрыт.
- Введите «GA». Ожидается один элемент: Gamma. Сопоставление без учёта регистра.

2. validation_error
- Введите «@@@». Ожидается сообщение об ошибке «Недопустимый фильтр…», виден полный список, empty state скрыт.

3. boundary_empty
- Введите «zzz». Ожидается пустое состояние (показывается «Ничего не найдено»), ошибок нет.

4. reset_returns_full
- Введите «ta». Ожидаются Beta и Delta (2 элемента). Нажмите «Сброс». Ожидается полный список, ошибок нет, empty state скрыт.

Дополнительно (консоль DevTools):
- Количество элементов: `document.querySelectorAll('#list li').length`
- Видимость ошибки: `document.getElementById('error').hidden`
- Видимость empty: `document.getElementById('empty').hidden`

## Спеки и контракт

- Спеки (SpecKit YAML): practices/practice_05/specs/skit/
- Контракт: practices/practice_05/contract.md
- Проверки: practices/practice_05/checks.md
- Рефлексия: practices/practice_05/reflection.md

## Устранение неполадок

- Порт занят: используйте другой порт (например, 8088) или остановите работающий сервер.
- Из Windows не открывается localhost: используйте bind 0.0.0.0 и заходите по IP WSL.
