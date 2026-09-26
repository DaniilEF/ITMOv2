# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| API ↔ Валидатор | Отсутствует поле `diff` | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{}' | Текущее: 500 (KeyError). Целевое: 422 Unprocessable Entity с сообщением об отсутствии `diff` | TRAINING_PR.diff: app/api.py 35-37; CASE.md (вход: POST /api/reviews); prompts.md P1-01 |
| API ↔ Валидатор | Неверный тип `diff` (число вместо строки) | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":123}' | Целевое: 422 Unprocessable Entity; указание на тип. Текущее: уточнить фактический код | TRAINING_PR.diff: app/api.py 35-37; app/review_service.py 19-21; TODO: подтвердить текущий ответ |
| API ↔ Валидатор | Пустая строка в `diff` | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":""}' | Целевое: 422 или 400 (пустое значение не принимается). Текущее: вероятно 200 (проксирование) | TRAINING_PR.diff: app/api.py 35-37; app/review_service.py 19-22; TODO: согласовать код ответа |
| API ↔ Валидатор (API-1) | Превышение лимита размера (>20000) | payload_large.json с `diff` длиной 20001 'a'; curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d @payload_large.json | 413 Payload Too Large; запрос не уходит в ReviewService/LLM | CASE.md (API-1); TRAINING_PR.diff: app/api.py 35-37 |
| API ↔ ReviewService (OUT-1) | Контракт ответа не соответствует OUT-1 | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":"+ file.py\n+ print(1)"}' | Целевое: JSON по OUT-1: summary; risks (<=3, с file,line,evidence,risk); checks. Текущее: {comment} | CASE.md (OUT-1); TRAINING_PR.diff: app/review_service.py 19-22 |
| ReviewService ↔ LLM (REL-1) | Таймаут внешнего вызова | Эмулировать задержку LLM >10s (стаб/прокси), затем POST | Контролируемый ответ без 5xx; явное указание таймаута | CASE.md (REL-1); prompts.md P1-02 |
| ReviewService ↔ LLM (SEC-1) | Нет санитайза секретов | POST diff с маркером токена ("token=TEST"/"ghp_TEST"); стаб LLM возвращает принятый prompt | В prompt секреты замаскированы: [REDACTED]. Текущее: уходят сырые значения | CASE.md (SEC-1); TRAINING_PR.diff: app/review_service.py 20-22 |
| API/Service ↔ Логи (OBS-1) | Логируются сырые `diff` и ответы LLM | Включить DEBUG; отправить POST с уникальным маркером ZX-OBS-1 | В логах нет сырых diff/ответов; только request_id, длительность, статус | CASE.md (OBS-1) |
| Сервис ↔ Внешние системы (SCOPE-1) | Выполняются действия (approve/merge/edit) | Аудит кода; мониторинг исходящих HTTP при POST | Действия не выполняются; только совет | CASE.md (SCOPE-1); app/* |
| Формирование рисков (QA-1) | Риски без подтверждения evidence | POST с diff без проблем; затем с одной явной проблемой | Либо 0 рисков, либо каждый риск имеет evidence (file,line) или ссылку на правило; всего ≤3 | CASE.md (QA-1, OUT-1) |
| Совместимость типов | `dict[str, str]` ломает совместимость/схемы | Проверка под Python<3.9 или генерация OpenAPI | Целевое: совместимые аннотации/схемы; отсутствие падений | TRAINING_PR.diff: app/api.py 36; app/review_service.py 19; prompts.md P1-01 |
| Доступность API | Маршрут `/health` доступен | curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/health | 200 OK; тело {"status":"ok"} | TRAINING_PR.diff: app/api.py 40-42 |

## Как использовали AI

- Метод: Tree of Thoughts. Рассмотрены альтернативные ветви для расширения покрытия: (A) добавить только правила SEC/API/REL/OUT; (B) включить валидацию входа и совместимость типов; (C) добавить наблюдаемость и границы SCOPE/логов. Оценка ветвей по критериям: полнота правил (CASE.md), воспроизводимость шагов, проверяемость результатов, отсутствие домыслов. Выбрана комбинированная ветвь B+C с минимально достаточным набором сценариев (12) и явными ожиданиями.
- Источники фактов: CASE.md (SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1); TRAINING_PR.diff (изменения app/api.py, app/review_service.py); prompts.md (P1-01, P1-02).

## Проверка качества документа

- [ ] Все правила SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1 покрыты отдельными сценариями.
- [ ] Для каждого кейса есть чёткие шаги (curl/HTTP) и проверяемые ожидания (коды, структура, отсутствие побочных эффектов).
- [ ] Там, где реализация отстаёт от правил, указаны текущее vs целевое ожидания без домыслов; отмечены TODO для уточнений.
- [ ] Evidence указывает на реальные артефакты (CASE.md, TRAINING_PR.diff, prompts.md) и корректные участки кода.
- [ ] Присутствуют негативные кейсы: отсутствие/тип/пустой diff, длина >20000, таймаут.
- [ ] Отсутствие логирования сырых данных проверяется на DEBUG (OBS-1).
