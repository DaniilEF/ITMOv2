Выжимка проекта — AGENTS MVP

Обзор
- Назначение: сервис принимает код/дифф и логи упавших тестов и возвращает до 3 точных подсказок с цитатами. Только консультации (без автоматических правок).
- Соответствие спецификации: SEC-1, API-1, REL-1, OUT-1, QA-1, SCOPE-1, OBS-1 из AGENTS.md.

Реализовано
- HTTP-сервис: server.py (только стандартная библиотека Python)
  - Эндпоинт: POST /api/hints
  - Запрос: { diff: string|null, code_bundle: [{path, content}], test_output: string, lang: "ru"|"en" }
  - Ответы:
    - 200 OK: { summary, hints (≤3 с полями file,line,hint,evidence), checks }
    - 413 Payload Too Large при суммарном входе > 20000 символов (API-1)
  - Безопасность (SEC-1): маскировка Bearer/ghp_/AWS ключей, паролей, приватных ключей.
  - Селектор: извлекает file:line из test_output и возвращает контекст ±20 строк из code_bundle; небольшие файлы оставляет целиком.
  - Конструктор промпта: компактирует вход для LLM.
  - LLM‑клиент (REL-1): таймаут 10 сек; при таймауте/ошибке — контролируемый деградированный ответ.
  - Валидатор (OUT-1, QA-1): оставляет только подсказки, у которых evidence встречается во входе; максимум 3.
  - Локализация: ru|en для шаблонов summary/checks.
  - Наблюдаемость (OBS-1): логируются только метаданные (метод/путь/длина).

Интеграция MCP и автопроверка
- practices/practice_04/opencode.json: зарегистрирован MCP "tessl" и собственный "agents-mcp" (команда переведена на python3).
  - Локальная команда через bash -lc: при отсутствии Node устанавливает/использует nvm + Node 20, затем запускает npx @tessl/cli mcp start.
  - Сохранён файловый MCP для practice_04.
  - Добавлен pre-commit hook для автозапуска проверки через skill.

Запуск
- Старт сервиса:
  python practices/practice_04/server.py
- Переменные окружения (опционально): AGENTS_HOST (по умолчанию 127.0.0.1), AGENTS_PORT (по умолчанию 8080)
- Пример запроса:
  curl -sS -X POST http://127.0.0.1:8080/api/hints \
    -H "Content-Type: application/json" \
    -d '{"diff": null, "code_bundle": [{"path":"foo.py","content":"def x():\n    return 1\n"}], "test_output": "foo.py:2: AssertionError", "lang": "ru"}'

Изменённые файлы
- Добавлен: practices/practice_04/server.py
- Изменён: practices/practice_04/opencode.json (MCP tessl)
- Сохранён diff: practices/practice_04/feature.diff
 - Добавлены линтер и форматтер в стиле Google: .pylintrc, .style.yapf, requirements-dev.txt

Следующие шаги
- Добавить тесты (валидация схемы, покрытие санитайзера, крайние случаи селектора).
- Подключить реальный вызов LLM за таймаут-обёрткой.
- При необходимости добавить ограничение частоты запросов.
- Запустить линтер и форматтер: 
  - python -m pip install -r practices/practice_04/requirements-dev.txt
  - pylint practices/practice_04
  - yapf -r -i practices/practice_04
- Установить pre-commit и активировать хук автопроверки:
  - python3 -m pip install pre-commit
  - pre-commit install
  - pre-commit run --all-files
