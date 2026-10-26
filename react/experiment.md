# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| API ↔ Валидатор | Нет поля `diff` в теле | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{}' | Текущее: 500 (KeyError). Целевое: 422 Unprocessable Entity c сообщением об отсутствии поля `diff` | TRAINING_PR.diff: app/api.py 35-37; CASE.md (вход POST /api/reviews); prompts.md P1-01 |
| API ↔ Валидатор | Неверный тип `diff` (число) | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":123}' | Целевое: 422 Unprocessable Entity (ожидается строка). Текущее: возможно 200 — уточнить фактический код | TRAINING_PR.diff: app/api.py 35-37; app/review_service.py 19-21; TODO: подтвердить текущий ответ |
| API ↔ Валидатор | Пустая строка в `diff` | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":""}' | Целевое: 422 или 400 за пустое значение. Текущее: вероятно 200 (проксирование в LLM) | TRAINING_PR.diff: app/api.py 35-37; app/review_service.py 19-22; TODO: согласовать код ответа |
| API ↔ Валидатор (API-1) | Длина `diff` > 20000 | Сформировать payload_large.json с `diff` длиной 20001 'a'; curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d @payload_large.json | 413 Payload Too Large; запрос не уходит в ReviewService/LLM | CASE.md (API-1); TRAINING_PR.diff: app/api.py 35-37 |
| API ↔ ReviewService (OUT-1) | Контракт ответа не соответствует OUT-1 | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":"+ file.py\n+ print(1)"}' | Целевое: JSON со schema OUT-1 (summary; risks<=3 с file,line,evidence,risk; checks). Текущее: {comment} | CASE.md (OUT-1); TRAINING_PR.diff: app/review_service.py 19-22 |
| ReviewService ↔ LLM (REL-1) | Таймаут внешнего вызова | Эмулировать задержку LLM >10s (стаб/прокси), затем выполнить POST | Контролируемый ответ без 5xx; явное указание, что сработал timeout по REL-1 | CASE.md (REL-1); prompts.md P1-02 |
| ReviewService ↔ LLM (SEC-1) | Секреты не маскируются перед LLM | POST diff с маркером токена: "token=TEST" или "ghp_TEST"; стаб LLM возвращает принятый prompt | В prompt секреты замаскированы: [REDACTED]; сырые значения не уходят | CASE.md (SEC-1); TRAINING_PR.diff: app/review_service.py 20-22 |
| API/Service ↔ Логи (OBS-1) | Логируются сырые `diff`/ответы LLM | Включить DEBUG-логи; отправить POST с уникальным маркером, например "ZX-OBS-1" | Логи не содержат сырых diff/ответов; пишутся только request_id, длительность, статус | CASE.md (OBS-1) |
| Сервис ↔ Внешние системы (SCOPE-1) | Выполнение действий (approve/merge/edit) | Аудит кода и мониторинг исходящих HTTP при POST | Никаких действий вне советов; только формирование ответа | CASE.md (SCOPE-1); app/* |
| Формирование рисков (QA-1) | Риски без подтверждения evidence | POST с diff без проблем; затем с одной явной проблемой | Либо 0 рисков, либо каждый риск с evidence (file,line) или ссылкой на правило; всего рисков <=3 | CASE.md (QA-1, OUT-1) |
| Совместимость типов | `dict[str, str]` может ломать схемы/версии | Проверка под Python < 3.9 или генерация OpenAPI | Целевое: совместимые аннотации/схемы; отсутствие падений | TRAINING_PR.diff: app/api.py 36; app/review_service.py 19; prompts.md P1-01 |
| Доступность API | Маршрут зарегистрирован и отвечает | curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health | 200 OK; стабильный ответ {"status":"ok"} | TRAINING_PR.diff: app/api.py 40-42 |

## Как использовали AI

- Метод: ReAct (Reasoning + Action) на основе репозитория. Факты брались из CASE.md (SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1), TRAINING_PR.diff (изменения app/api.py, app/review_service.py) и prompts.md (P1-01, P1-02).
- Действия: сформулированы сценарии, сопоставлены с правилами, даны пошаговые способы воспроизведения и проверяемые ожидания; зафиксированы текущие расхождения и целевые состояния.

## Проверка качества документа

- [ ] Покрыты все правила SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1 отдельными сценариями.
- [ ] Для каждого кейса есть чёткие шаги и проверяемые ожидания (HTTP-коды, структура тела, отсутствие побочных эффектов).
- [ ] Там, где реализация отстаёт от правил, указаны текущее и целевое поведение без домыслов.
- [ ] Evidence ссылается на реальные артефакты (CASE.md, TRAINING_PR.diff, prompts.md) и корректные участки кода.
- [ ] Присутствуют негативные кейсы: отсутствие/тип/пустой diff, длина >20000, таймаут.
- [ ] Отсутствует логирование сырых данных (OBS-1) — предусмотрена проверка на DEBUG.
