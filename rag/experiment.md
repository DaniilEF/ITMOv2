# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| API ↔ Валидатор | Нет поля `diff` в теле | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{}' | Текущее: 500 (KeyError). Целевое: 422 Unprocessable Entity с сообщением об отсутствии `diff` | TRAINING_PR.diff: app/api.py 35-37; prompts.md P1-01; CASE.md (вход POST /api/reviews) |
| API ↔ Валидатор | Неверный тип `diff` (число вместо строки) | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":123}' | Целевое: 422 Unprocessable Entity с пояснением о типе. Текущее: возможно 200 (строковое приведение в prompt). Уточнить фактическое поведение | TRAINING_PR.diff: app/api.py 35-37; app/review_service.py 19-21; TODO: подтвердить текущий код ответа |
| API ↔ Валидатор | Пустая строка в `diff` | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":""}' | Целевое: 422 или 400 за пустое значение; Текущее: вероятно 200 (проксирование в LLM) | TRAINING_PR.diff: app/api.py 35-37; app/review_service.py 19-22; TODO: согласовать код ответа |
| API ↔ Валидатор (API-1) | Превышение лимита размера (>20000) | Сформировать payload_large.json с полем `diff` длиной 20001 символ: curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d @payload_large.json | Целевое: 413 Payload Too Large. Текущее: нет отсечения, запрос уходит в ReviewService/LLM | CASE.md (API-1); TRAINING_PR.diff: app/api.py 35-37 |
| API ↔ ReviewService (OUT-1) | Контракт ответа не соответствует OUT-1 | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":"+ file.py\n+ print(1)"}' | Целевое: 200 OK и JSON со схемой OUT-1: summary; risks (<=3, с file,line,evidence,risk); checks. Текущее: возвращается {comment} | CASE.md (OUT-1); TRAINING_PR.diff: app/review_service.py 19-22 |
| ReviewService ↔ LLM (REL-1) | Таймаут внешнего вызова | Эмулировать задержку ответа LLM >10s (стаб/прокси), затем выполнить POST как выше | Целевое: контролируемый ответ без 5xx; сообщение об истечении времени (REL-1). Текущее: поведение неизвестно — зафиксировать факт | CASE.md (REL-1); prompts.md P1-02 |
| ReviewService ↔ LLM (SEC-1) | Отсутствует санитайз секретов перед LLM | Отправить diff с тестовым токеном вида "token=TEST" или "ghp_xxx"; через стаб LLM вернуть принятый prompt | В prompt, принятым LLM, секреты замаскированы ([REDACTED]); Текущее: секреты уходят в prompt без маскировки | CASE.md (SEC-1); TRAINING_PR.diff: app/review_service.py 20-22 |
| API/Service ↔ Логи (OBS-1) | Логирование сырых `diff` и ответов LLM | Включить DEBUG-логи, отправить POST с уникальным маркером (например, `ZX-OBS-1`) | В логах отсутствуют сырые содержимое diff/ответы LLM; пишутся только метаданные (request_id, длительность, статус) | CASE.md (OBS-1) |
| Сервис ↔ Внешние системы (SCOPE-1) | Сервис выполняет действия (approve/merge/edit) | По коду: поиск вызовов действий; Интеграционно: мониторинг сетевых обращений при POST | Отсутствуют вызовы approve/merge/edit; сервис только советует | CASE.md (SCOPE-1); prompts.md P1-02 |
| Формирование рисков (QA-1) | Риски без подтверждения diff или правилом | POST с diff без проблем; затем с одной явной проблемой | В ответе либо 0 рисков, либо каждый риск имеет evidence (file,line) или ссылку на правило; всего рисков <=3 | CASE.md (QA-1, OUT-1) |
| API ↔ Ошибки схемы | Несогласованность типов `dict[str, str]` (совместимость) | В среде Python <3.9 или при генерации OpenAPI — вызвать POST | Целевое: устойчивость схем; Текущее: риск несоответствия типов | prompts.md P1-01; TRAINING_PR.diff: app/api.py 36; app/review_service.py 19 |

## Как использовали AI

- Источники (RAG): CASE.md (SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1); TRAINING_PR.diff (фактические изменения app/api.py, app/review_service.py); prompts.md (P1-01, P1-02 — предварительный анализ и master prompt).
- Проверка вручную: сопоставление каждого сценария с правилом/фрагментом diff; уточнение текущего vs целевого поведения. Для пустого `diff` и неверного типа помечены TODO на подтверждение фактических кодов.

## Проверка качества документа

- [ ] Покрыты SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1 отдельными сценариями.
- [ ] Шаги воспроизведения однозначны; есть curl/HTTP и способы инъекции отказов (таймаут, большой diff, невалидный вход).
- [ ] Указаны текущие и целевые ожидания там, где реализация отстаёт от правил.
- [ ] Контракт OUT-1 описан: summary; risks (<=3, file,line,evidence,risk); checks.
- [ ] Evidence ссылается на реальные артефакты: CASE.md, TRAINING_PR.diff, prompts.md.
- [ ] Негативные кейсы присутствуют: 413, таймаут, отсутствие `diff`.
- [ ] Отсутствие логирования содержимого проверено на DEBUG (OBS-1).
- [ ] Термины и идентификаторы правил использованы единообразно.
