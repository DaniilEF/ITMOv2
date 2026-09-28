# Integration-проверки

| Связь компонентов | Что может сломаться | Как воспроизводим | Ожидаемый результат | Evidence |
|---|---|---|---|---|
| API ↔ Валидатор | Отсутствует поле `diff` | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{}' | 422 Unprocessable Entity с описанием ошибки валидации поля `diff` | app/api.py:35-38, CASE.md (вход: POST /api/reviews) |
| API ↔ Валидатор | `diff` не строка (тип int) | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":123}' | 422 Unprocessable Entity; тело с деталями ошибки типа | app/api.py:35-38 |
| API ↔ Валидатор | Пустая строка в `diff` | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":""}' | 422 или 400 за пустое значение; решение уточнить | app/api.py:35-38, TODO: подтвердить код ответа |
| API ↔ Валидатор (API-1) | Превышен лимит размера diff (>20000) | Подать тело с "diff" длиной 20001 символ (например, файл payload_large.json с полем diff на 20001 'a'; curl -X POST ... -d @payload_large.json) | 413 Payload Too Large | CASE.md (API-1), app/api.py |
| API ↔ ReviewService (OUT-1) | Несоответствие контракта ответа | curl -X POST http://localhost:8000/api/reviews -H "Content-Type: application/json" -d '{"diff":"+ file.py\n+ print(1)"}' | Целевое: 200 OK и JSON со схемой OUT-1: fields summary, risks (<=3, с file,line,evidence,risk), checks. Текущее: возвращается {comment} (несоответствие контракту) | CASE.md (OUT-1), app/review_service.py:23, TRAINING_PR.diff |
| ReviewService ↔ LLM (REL-1) | Таймаут внешнего вызова | Эмуляция задержки LLM >10s (стаб/проксирование); затем POST как выше | 200 OK или контролируемый ответ без 5xx; сообщение об истечении времени по REL-1 | CASE.md (REL-1), app/review_service.py |
| ReviewService ↔ LLM (SEC-1) | Секреты не санитайзятся перед отправкой | POST с diff, содержащим маркер токена (например, "ghp_..."), при подключенном тестовом LLM-стабе, который возвращает принятый prompt | В принятый LLM prompt секреты замаскированы ([REDACTED]); ни один секретный шаблон не утекает | CASE.md (SEC-1), app/review_service.py:16 |
| API/Service ↔ Логи (OBS-1) | Логирование сырых diff/ответов LLM | Включить DEBUG-логи, выполнить POST с уникальным маркером в diff | В логах отсутствуют сырые содержимое diff и ответы LLM; чувствительные данные не пишутся | CASE.md (OBS-1), app/* |
| Сервис ↔ Внешние системы (SCOPE-1) | Сервис выполняет действия (approve/merge/edit) | По коду: поиск вызовов действий; Интеграция: наблюдать сетевые обращения при POST | Нет вызовов approve/merge/edit; только формирование совета. Никаких побочных действий | CASE.md (SCOPE-1), app/* |
| Формирование рисков (QA-1) | Риски без подтверждения строкой diff или правилом | POST с diff, не содержащим проблем; затем POST с diff, содержащим одну явную проблему | В ответе либо 0 рисков, либо каждый риск имеет evidence (file,line) или ссылку на правило; общее число рисков <=3 | CASE.md (QA-1, OUT-1), TRAINING_PR.diff |

## Как использовали AI

- Использованные промпты: prompts.md: P1-01, P1-02.
- Что проверили вручную: соответствие каждому правилу (SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1); воспроизводимость curl-примеров; корректность ссылок на исходники. Для пустого `diff` помечено TODO на уточнение кода ответа.

## Проверка качества документа

- [ ] Все правила SEC-1, API-1, REL-1, OUT-1, SCOPE-1, QA-1, OBS-1 покрыты отдельными сценариями.
- [ ] Шаги воспроизведения однозначны; есть curl/HTTP примеры и способы инъекции отказов.
- [ ] Ожидаемые HTTP-коды указаны явно; отмечены места для уточнения (TODO) и план проверки факта.
- [ ] Схема OUT-1 описана и проверяется: summary, risks (<=3, file,line,evidence,risk), checks.
- [ ] Нет домыслов сверх CASE.md и исходников; Evidence ссылается на реальные файлы и известные строки.
- [ ] Негативные кейсы присутствуют: таймаут, 413, невалидный вход.
- [ ] Проверено отсутствие логирования сырых данных (OBS-1) на DEBUG-уровне.
- [ ] Термины и идентификаторы правил использованы единообразно по документу.
