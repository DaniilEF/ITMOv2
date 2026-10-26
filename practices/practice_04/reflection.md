Практика 4 — рефлексия по реализации среды агента, skill и собственного MCP

Что помогло
- Четкие правила и поток из AGENTS.md: сразу понятны границы (SEC-1, API-1, REL-1, OUT-1, QA-1, SCOPE-1, OBS-1) и критерии приема.
- Готовый MVP сервиса (server.py) и опорные материалы (SUMMARY.md, AGENTS.md) ускорили интеграцию.
- Конфиг opencode.json уже содержал полезные MCP (filesystem, tessl), что упростило объяснение подключений и расширение.

Что мешало
- В окружении отсутствовали pip/ensurepip/venv, из-за чего не получалось сразу поставить линтер/форматтер. Обошли это, а затем установили python3-venv и настроили .venv.
- Несовместимость путей/движка запуска: skill по умолчанию стартовал MCP командой "python ..."; в системе нет alias "python". Перевели на "python3" и передали env в subprocess.
- Разный формат обертки контента в MCP-ответе: пришлось заложить fallback, чтобы корректно извлекать OUT-1 из разных структур ({body}/{json}/inline).

Где вмешивались вручную
- Написан собственный MCP-сервер на Python (stdio JSON-RPC): practices/practice_04/mcp/agents_mcp.py, tool agents.hints.call вызывает POST /api/hints.
- Реализован skill-оркестратор: practices/practice_04/skills/agents_qa.py. Он стартует MCP, вызывает tool, валидирует OUT-1 и QA-1, обрабатывает статусы ошибок (в т.ч. 413).
- Обновлен opencode.json: добавлено подключение "agents-mcp" с локальным запуском Python-скрипта.
- Добавлены образцы входов: success_payload.json, error_payload_long.json (для API-1 413), sec1_payload.json (для SEC-1/OBS-1).
- Минимальные правки server.py под линтер: короткие docstring, переименование параметра log_message(format->fmt), точечные отключения предупреждений (line-too-long, broad-exception-caught, complexity) без изменения логики.

Подтвержденные сценарии и результаты
- REL-1 (деградация по умолчанию): ответ 200 OK с контролируемым телом "Внешний ассистент недоступен...", hints=[], checks=[...].
- REL-1 (без деградации): при AGENTS_MVP_SIMULATE_TIMEOUT=0 сервер возвращает валидный OUT-1 с summary "No actionable hints detected.", hints=[], checks=[...].
- API-1: при входе > 20000 символов возвращается 413 Payload Too Large; skill корректно показывает ok=false с сообщением "HTTP 413 Payload Too Large".
- SEC-1: тестовые секреты (Bearer ghp_, AKIA...) не просачиваются в логи; сервер маскирует вход и не логирует содержимое (OBS-1).
- OUT-1/QA-1: валидатор skill-а проверяет форму и подтверждение evidence; на наших кейсах hints пустой массив, формат валиден.

Обоснование подключений
- filesystem-practice-04 (MCP): удобен для чтения локальных файлов и подготовки code_bundle без прямого доступа к ФС со стороны агента.
- agents-mcp (собственный MCP): инкапсулирует вызов /api/hints в единый tool (agents.hints.call) и нормализует результаты/ошибки на стороне MCP.
- tessl (опционально): пример дополнительного MCP для расширения инструментов (в текущей демонстрации не обязателен).

Выводы
- MVP покрывает ключевые правила SEC-1, API-1, REL-1, OUT-1, QA-1, OBS-1; деградация при недоступности LLM работает безопасно, схема ответа валидна.
- Skill-оркестратор и MCP-tool обеспечивают воспроизводимые проверки и изоляцию логики вызова сервиса.
- Основные сложности были инфраструктурные (python/pip/venv), а не алгоритмические. После настройки .venv линтер/форматтер интегрировались без проблем.
- Следующие шаги: автотесты для санитайзера и селектора, реальный LLM-клиент под таймаут-оберткой, ограничение частоты, подключение pre-commit.

Демо-чеклист (для защиты)
1. Старт сервиса: AGENTS_HOST=127.0.0.1 AGENTS_PORT=8080 python3 practices/practice_04/server.py
2. Успешный сценарий через skill: python3 practices/practice_04/skills/agents_qa.py --payload practices/practice_04/samples/success_payload.json
3. REL-1 деградация (по умолчанию) и без деградации (AGENTS_MVP_SIMULATE_TIMEOUT=0) — показать разные summary.
4. API-1: payload > 20k (error_payload_long.json) — увидеть ok=false и статус 413.
5. SEC-1/OBS-1: sec1_payload.json — отсутствие секретов в логах, валидный ответ.
6. Пояснить подключения: filesystem (чтение файлов), agents-mcp (tool для /api/hints), tessl (опционально).
