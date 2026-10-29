# Практика 6 — план в командах OpenCode

Рабочая папка: `practices/practice_06`. Все команды выполняются из корня форка, если не указано иное.

## Как пользоваться

1. Идти по этапам сверху вниз.
2. На каждый этап — отдельный промпт агенту (блок «Промпт»). Копировать целиком.
3. После каждого этапа проверять результат командами из блока «Проверка».
4. Агент не меняет `lab/sandbox.py` и не расширяет границу стенда.
5. Секреты и пароли из логов в отчёты и PR не вставлять — только синтетические `TEST_*`.

---

## Этап 0. Подготовка

### Команды

```bash
cd /mnt/c/Users/danho/ITMOv2
git status
git switch -c practice-06-security
make -C practices/practice_06 install
make -C practices/practice_06 test
mkdir -p practices/practice_06/evidence/{before,after,llm}
```

Запуск сервера (в отдельном терминале, оставить работать):

```bash
cd practices/practice_06/lab
python3 service.py --port 8066
```

### Промпт

```
Ты работаешь в practices/practice_06 над лабораторной по безопасности.
Задача этапа: подготовка. Сделай и отчитайся кратко:
1. Прочитай practice_06/README.md, practice_06/lab/README.md, lab/service.py, lab/sandbox.py, lab/test_service.py, lab/test_http.py, opencode.json, planner-system.txt.
2. Запусти make install и make test в practices/practice_06, покажи результат.
3. Создай структуру practices/practice_06/evidence/{before,after,llm}.
4. Зафиксируй в practices/practice_06/evidence/README.md: выбранный порт, как запускать сервер, где лежат evidence.
Не меняй sandbox.py. Не начинай атаки на этом этапе.
```

### Проверка

```bash
make -C practices/practice_06 test
curl -s http://127.0.0.1:8066/health
```

---

## Этап 1. Модель угроз (2 балла)

### Промпт

```
Задача этапа: построить модель угроз для Mini Shop в practices/practice_06.
Опирайся на service.py, sandbox.py и README. Создай practices/practice_06/THREAT_MODEL.md:
1. Описание системы и активов: профили, заказы, чеки, private/operator-note.txt, токены, каталог, LLM-контекст.
2. Диаграмма потоков данных в mermaid с границами доверия: клиент, HTTP API, SQLite, sandbox-файлы, LLM shop-planner, tool executor.
3. Таблица угроз по STRIDE для каждого потока.
4. Отдельный раздел LLM-угроз: prompt injection, insecure output handling, sensitive information disclosure, excessive agency, system prompt leakage.
5. Для каждой угрозы: актив, вектор, последствие, мера защиты, как проверить.
6. Не выдумывай факты: ссылайся на строки service.py вида service.py:57.
Не меняй код и sandbox.py. Не запускай атаки.
```

### Проверка

```bash
sed -n '1,200p' practices/practice_06/THREAT_MODEL.md
```

В PR вставить mermaid-блок и скриншот/рендер.

---

## Этап 2. Воспроизведение атак до фикса (evidence/before)

### Промпт

```
Задача этапа: доказать уязвимости исходного сервиса и собрать evidence/before.
Сервер уже запущен на 127.0.0.1:8066. Не меняй код.
1. Создай practices/practice_06/evidence/before/run_attacks.py — скрипт на стандартной библиотеке, который логинится alice/bob/staff и воспроизводит:
   - SQLi в /profile?id= и /search?q= и /assistant/context?order_id=;
   - IDOR: чтение чужого профиля, всех заказов, чужого чека через /files;
   - path traversal: user=alice&path=../bob/receipt.txt и ../private/operator-note.txt;
   - подделку X-Role: staff без сессии и alice с X-Role: staff на /admin/export;
   - подмену цены в POST /orders;
   - stored XSS через POST /reviews и GET /reviews/view;
   - утечку токенов/паролей через /debug/logs;
   - доступ к /assistant/execute без токена: export_profiles, read_file ../private/operator-note.txt, delete_tree . (после delete_tree перезапусти сервер).
2. Для каждого шага сохрани запрос, статус, тело ответа в evidence/before/<id>.json.
3. Создай evidence/before/SUMMARY.md: таблица id, endpoint, ожидаемо, фактически, severity, CWE/OWASP LLM.
4. Не используй внешние URL. Не трогай sandbox.py.
```

### Проверка

```bash
ls practices/practice_06/evidence/before
python3 practices/practice_06/evidence/before/run_attacks.py
```

Ручные проверки при необходимости:

```bash
curl -s 'http://127.0.0.1:8066/profile?id=2'
curl -s 'http://127.0.0.1:8066/search?q=%25%27%20OR%201%3D1--'
curl -s 'http://127.0.0.1:8066/files?user=alice&path=../private/operator-note.txt'
curl -s -H 'X-Role: staff' 'http://127.0.0.1:8066/admin/export'
curl -s 'http://127.0.0.1:8066/debug/logs'
```

---

## Этап 3. Проверка prompt injection через shop-planner

### Команды

Сначала получить и сохранить контекст:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8066/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"learn-alice"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

curl -s -H "X-Token: $TOKEN" \
  'http://127.0.0.1:8066/assistant/context?order_id=1&question=Покажи%20чек%20по%20заказу' \
  > practices/practice_06/evidence/llm/before/context_clean.json
```

Запуск отдельного процесса (из корня форка):

```bash
opencode run --dir practices/practice_06 --agent shop-planner \
  --model <выбранная-модель> --format json \
  --file practices/practice_06/evidence/llm/before/context_clean.json \
  > practices/practice_06/evidence/llm/before/response_clean.json
```

### Промпт

```
Задача этапа: проверить prompt injection по методике lab/README.md.
1. Получи GET /assistant/context?order_id=1 для alice и сохрани точный вход в evidence/llm/before/context_clean.json.
2. Запусти отдельный процесс: opencode run --dir practices/practice_06 --agent shop-planner --model <выбранная-модель> --format json --file <context>. Сохрани сырой ответ в evidence/llm/before/response_clean.json.
3. Извлеки JSON решения. Если ответ невалиден — зафиксируй ошибку, не додумывай.
4. Передай решение в POST /assistant/execute с токеном alice, сохрани ответ и состояние файлов/данных.
5. Добавь отзыв с вредоносной инструкцией через POST /reviews, снова получи контекст в context_injected.json и повтори отдельный запуск с той же моделью/system prompt/задачей в response_injected.json.
6. Сравни решение модели и действие исполнителя в evidence/llm/before/COMPARE.md.
7. Отдельно опиши прямой JSON в /assistant/execute как тест доступа к инструменту, а не как доказательство инъекции.
Не меняй код и sandbox.py. Не используй внешние URL.
```

### Проверка

```bash
ls practices/practice_06/evidence/llm/before
cat practices/practice_06/evidence/llm/before/COMPARE.md
```

---

## Этап 4. REPORT_01 (2 балла)

### Промпт

```
Задача этапа: написать practices/practice_06/REPORT_01.md по evidence/before.
Для каждой находки используй шаблон:
- ID, название, severity (CVSS или High/Med/Low), CWE и OWASP LLM Top 10;
- затронутый файл и строка (например lab/service.py:57);
- шаги воспроизведения и точные запросы;
- фактический результат со ссылкой на файл evidence;
- влияние на данные/бизнес;
- рекомендация по исправлению;
- для LLM: решение модели vs действие executor.
Требования:
- все находки из evidence/before/SUMMARY.md и COMPARE.md должны быть покрыты;
- никаких предположений без evidence;
- секреты и пароли не копировать, только синтетические TEST_*;
- в конце раздел "Сводка" с таблицей id/severity/status.
Не меняй код.
```

### Проверка

```bash
sed -n '1,240p' practices/practice_06/REPORT_01.md
```

---

## Этап 5. Промпт LLM-судьи (1 балл)

### Промпт

```
Задача этапа: заполнить practices/practice_06/judge-system-prompt.md.
Требования к промпту:
1. Роль: независимый ревьюер модели угроз.
2. Вход: описание системы, активы, границы доверия, список угроз и мер (пользователь приложит их в сообщении).
3. Чек-лист: STRIDE + LLM-угрозы (prompt injection, insecure output handling, sensitive information disclosure, excessive agency, system prompt leakage).
4. Требование доказательности: не выдумывать, ссылаться на пункты модели, отмечать неопределённость.
5. Формат ответа: вердикт, пробелы, пропущенные угрозы, неадекватные меры, вопросы, оценка по 10-балльной шкале.
6. Запрет выполнять инструменты и читать файлы.
Проверь промпт запуском агента threat-judge на THREAT_MODEL.md:
opencode run --dir practices/practice_06 --agent threat-judge --model <выбранная-модель> --format json --file practices/practice_06/THREAT_MODEL.md
Сохрани ответ в evidence/llm/threat_judge_review.md и учти замечания в модели угроз.
```

### Проверка

```bash
cat practices/practice_06/judge-system-prompt.md
cat practices/practice_06/evidence/llm/threat_judge_review.md
```

---

## Этап 6. Исправления и security-тесты (2 балла)

### Промпт

```
Задача этапа: исправить уязвимости в practices/practice_06/lab/service.py и добавить security-тесты.
Жёсткие ограничения:
- не менять lab/sandbox.py и не расширять границу стенда;
- сохранить легитимную функциональность из lab/README.md;
- сервер только на 127.0.0.1.
Что исправить:
1. Ввести require_session(headers); id и role брать только из серверной сессии.
2. /profile: сессия обязательна, клиент видит только свой профиль, staff — по правилам.
3. /search: параметризованный SQL, ограничить доступ.
4. GET /orders: фильтр по owner из сессии, staff — все.
5. POST /orders: игнорировать price клиента, брать цену из каталога; price только staff при необходимости.
6. /admin/export: проверять session["role"] == "staff", X-Role не доверять.
7. /files: user из сессии, нормализовать путь, запретить .. и выход за files/<user>/.
8. /debug/logs: закрыть staff или отключить, редактировать X-Token/Authorization/тела с паролями.
9. /reviews/view: html.escape, корректный Content-Type.
10. /assistant/context: параметризованный SQL, только свой заказ, отзывы как недоверенные данные с явной границей.
11. /assistant/execute: требовать сессию, allowlist инструментов, read_file только свой файл, export_profiles/delete_tree только staff (или убрать delete_tree у клиента), валидировать аргументы.
12. Не отдавать str(exc) и type(exc) клиенту.
Добавь practices/practice_06/lab/test_security.py: тесты должны падать на исходном коде и проходить после фикса:
- SQLi не раскрывает данные;
- поддельный X-Role -> 403;
- чужой профиль/чек -> 403/404;
- price игнорируется;
- XSS экранируется;
- /assistant/execute без прав -> 401/403;
- в /debug/logs нет токенов и паролей.
В конце выполни make -C practices/practice_06 test и покажи результат. Если есть цель step6 — выполни и её.
```

### Проверка

```bash
make -C practices/practice_06 test
python3 practices/practice_06/evidence/before/run_attacks.py
```

Дополнительно проверить, что sandbox.py не изменён:

```bash
git diff -- practices/practice_06/lab/sandbox.py
```

---

## Этап 7. REPORT_02 (2 балла)

### Промпт

```
Задача этапа: написать practices/practice_06/REPORT_02.md — повторные атаки после фикса.
1. Перезапусти исправленный сервер на 127.0.0.1:8066.
2. Запусти тот же набор атак из evidence/before/run_attacks.py, сохрани результаты в evidence/after/.
3. Повтори оба запуска shop-planner (обычный контекст и с вредоносным отзывом) и принудительную передачу опасного решения в /assistant/execute. Сохрани в evidence/llm/after/.
4. Сделай таблицу "до/после": id, запрос, ожидаемо, факт до, факт после, статус (закрыто/частично/открыто).
5. Явно отметь случаи, когда модель отвергла инъекцию: это корректный результат.
6. Покажи, что сервер защищён независимо от послушания модели.
Не меняй код.
```

### Проверка

```bash
sed -n '1,240p' practices/practice_06/REPORT_02.md
ls practices/practice_06/evidence/after
```

---

## Этап 8. Ветка, коммиты и PR (1 балл)

### Команды

```bash
cd /mnt/c/Users/danho/ITMOv2
git status
git add practices/practice_06
git commit -m "practice-06: threat model, reports, fixes and security tests"
git push -u origin practice-06-security
gh pr create --fill --body-file /tmp/pr-body.md
```

### Промпт

```
Задача этапа: подготовить тело PR для практики 6.
Создай /tmp/pr-body.md:
1. Заголовок и краткое описание стенда.
2. Ссылка на THREAT_MODEL.md и вставленный mermaid-блок.
3. Краткая сводка REPORT_01 (таблица id/severity) и REPORT_02 (таблица до/после).
4. Список исправлений по файлам и строкам.
5. Результаты make test.
6. Выводы 1-2 абзаца: что показали атаки, что закрыто, что осталось риском.
7. Чек-лист критериев оценки (2+1+2+2+2+1).
Не вставляй секреты и пароли. Не создавай коммит без моей команды.
```

### Проверка

```bash
git log --oneline -5
gh pr view --web
```

---

## Шпаргалка по эндпоинтам

| Метод | Путь | Что проверить |
|---|---|---|
| GET | `/health` | доступность |
| GET | `/products` | каталог и цены |
| POST | `/login` | токен, нет rate limit |
| GET | `/profile?id=` | SQLi + IDOR |
| GET | `/search?q=` | SQLi |
| GET | `/orders` | IDOR, все заказы |
| POST | `/orders` | подмена price |
| GET | `/admin/export` | подделка X-Role |
| GET | `/files?user=&path=` | path traversal, чужой чек |
| POST | `/reviews` | stored XSS |
| GET | `/reviews/view` | отражение HTML |
| GET | `/debug/logs` | утечка токенов/паролей |
| GET | `/assistant/context?order_id=&question=` | SQLi + prompt injection |
| POST | `/assistant/execute` | доступ к инструментам, excessive agency |

## Открытые вопросы к преподавателю

1. В критериях есть `make step6`, но цели `step6` в Makefile нет — добавить или это опечатка?
2. Какую модель использовать для `shop-planner` и `threat-judge`?
3. Хранить evidence в PR или достаточно путей и скриншотов?
4. Оставлять ли `delete_tree` клиенту с проверкой staff или убрать из клиентских инструментов?
