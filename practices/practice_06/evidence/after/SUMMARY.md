# Evidence after — сводка атак на исправленный сервис

Base URL: `http://127.0.0.1:8066`; фикстуры синтетические.

| ID | Endpoint | Ожидаемо | Фактически | Severity | CWE | OWASP LLM | Evidence |
|---|---|---|---|---|---|---|---|
| 01-sqli-profile | GET /profile?id=1 OR 1=1 | Только профиль c id=1 | status=401, names=[] | High | CWE-89 | - | [01-sqli-profile.json](01-sqli-profile.json) |
| 02-idor-profile | GET /profile?id=2 | 403/404 для чужого профиля | status=403, names=[] | High | CWE-639 | - | [02-idor-profile.json](02-idor-profile.json) |
| 03-sqli-search | GET /search?q=' OR 1=1-- | Поиск только по совпадению | status=401, names=[] | High | CWE-89 | - | [03-sqli-search.json](03-sqli-search.json) |
| 04-idor-orders | GET /orders | Только заказы alice (owner=1) | status=200, owners=[1] | High | CWE-639 | - | [04-idor-orders.json](04-idor-orders.json) |
| 05-idor-file | GET /files?user=bob&path=receipt.txt | 403/404 для чужого чека | status=403, body={'error': 'forbidden'} | High | CWE-639 | - | [05-idor-file.json](05-idor-file.json) |
| 06-traversal-sibling | GET /files?user=alice&path=../bob/receipt.txt | 403/404 для выхода из своего каталога | status=400, body={'error': 'invalid path'} | High | CWE-22 | - | [06-traversal-sibling.json](06-traversal-sibling.json) |
| 07-traversal-private | GET /files?user=alice&path=../../private/operator-note.txt | 403/404 для приватного каталога | status=400, body={'error': 'invalid path'} | High | CWE-22 | - | [07-traversal-private.json](07-traversal-private.json) |
| 08-forged-role-anon | GET /admin/export (X-Role: staff) | 401/403 без валидной staff-сессии | status=401, rows=n/a | Critical | CWE-285 | - | [08-forged-role-anon.json](08-forged-role-anon.json) |
| 09-forged-role-alice | GET /admin/export (alice + X-Role: staff) | 403 для роли customer | status=403, rows=n/a | Critical | CWE-285 | - | [09-forged-role-alice.json](09-forged-role-alice.json) |
| 10-price-tampering | POST /orders {product: lamp, price: 1} | Цена из каталога 1500 | status=201, body={'id': 3, 'owner': 1, 'product': 'lamp', 'price': 1500} | Medium | CWE-602 | - | [10-price-tampering.json](10-price-tampering.json) |
| 11-stored-xss-store | POST /reviews | Текст сохраняется как данные | status=201, body={'saved': True} | Medium | CWE-79 | LLM02 | [11-stored-xss-store.json](11-stored-xss-store.json) |
| 12-stored-xss-view | GET /reviews/view | Тег экранирован как &lt;script&gt; | status=200, raw_script=False | Medium | CWE-79 | LLM02 | [12-stored-xss-view.json](12-stored-xss-view.json) |
| 13-logs-secret-leak | GET /debug/logs | Только staff; токены и пароли отредактированы | status=200, token=False, password=False | High | CWE-532 | - | [13-logs-secret-leak.json](13-logs-secret-leak.json) |
| 14-sqli-context | GET /assistant/context?order_id=0 OR 1=1 | Только заказ alice | status=400, chair=False, lamp=False | High | CWE-89 | LLM01 | [14-sqli-context.json](14-sqli-context.json) |
| 15-exec-export-noauth | POST /assistant/execute (export_profiles) | 401 без сессии | status=401, rows=n/a | Critical | CWE-306 | LLM06 | [15-exec-export-noauth.json](15-exec-export-noauth.json) |
| 16-exec-read-private | POST /assistant/execute (read_file private/operator-note.txt) | 401/403 для приватного файла | status=401, body={'error': 'login required'} | High | CWE-22 | LLM06 | [16-exec-read-private.json](16-exec-read-private.json) |
| 17-exec-delete-noauth | POST /assistant/execute (delete_tree .) | 401/403 без staff-сессии | status=401, body={'error': 'login required'} | High | CWE-306 | LLM06 | [17-exec-delete-noauth.json](17-exec-delete-noauth.json) |
| 18-delete-verify | GET /files?user=alice&path=receipt.txt | Файл на месте, ошибка не раскрывает внутренности | status=200, body={'content': 'TEST_ALICE receipt: chair, 5000 RUB'} | High | CWE-306 | - | [18-delete-verify.json](18-delete-verify.json) |
| 19-restart | GET /health | Сервер снова доступен | status=200, pid=2177 | Info | - | - | [19-restart.json](19-restart.json) |

## Выводы

- Чужие профили, заказы и файлы недоступны: проверяются сессия и владелец.
- SQL-инъекции в `/profile`, `/search` и `/assistant/context` не выполняются.
- Роль staff берётся только из сессии; заголовок `X-Role` игнорируется.
- Цена заказа берётся из каталога; поле `price` от клиента игнорируется.
- Отзывы экранируются, журнал доступен только staff и не содержит токенов/паролей.
- `/assistant/execute` требует сессию и роль: клиенту недоступны `export_profiles`, приватные файлы и `delete_tree`.
- После прогона стенд перезапущен; фикстуры не изменены.

Скрипт: [`run_attacks.py`](run_attacks.py).

## Принудительные решения executor с сессией клиента

| ID | Действие | Ожидаемо | Фактически | Evidence |
|---|---|---|---|---|
| 20-exec-export-alice | alice: `export_profiles` | 403 | 403 `forbidden` | [20-exec-export-alice.json](20-exec-export-alice.json) |
| 21-exec-read-private-alice | alice: `read_file private/operator-note.txt` | 403 | 403 `forbidden` | [21-exec-read-private-alice.json](21-exec-read-private-alice.json) |
| 22-exec-read-traversal-alice | alice: `read_file ../../private/operator-note.txt` | 400/403 | 400 `invalid path` | [22-exec-read-traversal-alice.json](22-exec-read-traversal-alice.json) |
| 23-exec-delete-alice | alice: `delete_tree(".")` | 403 | 403 `staff only` | [23-exec-delete-alice.json](23-exec-delete-alice.json) |
| 24-exec-read-bob-alice | alice: `read_file files/bob/receipt.txt` | 403 | 403 `forbidden` | [24-exec-read-bob-alice.json](24-exec-read-bob-alice.json) |
| 25-exec-read-own-alice | alice: `read_file files/alice/receipt.txt` | 200 | 200, чек alice | [25-exec-read-own-alice.json](25-exec-read-own-alice.json) |
| 26-exec-export-staff | staff: `export_profiles` | 200 | 200, два профиля | [26-exec-export-staff.json](26-exec-export-staff.json) |
| 27-files-after-forced | alice: чек после `delete_tree` | 200 | 200, файл не удалён | [27-files-after-forced.json](27-files-after-forced.json) |

Скрипт: [`run_forced_decisions.py`](run_forced_decisions.py).

## Аутентифицированные проверки

Полный набор: [`28-auth-checks.json`](28-auth-checks.json), скрипт [`run_auth_checks.py`](run_auth_checks.py).

| Проверка | Факт |
|---|---|
| `/profile?id=1 OR 1=1` с alice | 400 |
| `/profile?id=2` с alice | 403 |
| `/search?q=' OR 1=1--` с alice | 200, пустой список; чужих профилей нет |
| `/search?q=TEST` с alice | 200, только `TEST_ALICE` |
| `/orders` с alice | 200, `owners=[1]` |
| `/admin/export` alice + `X-Role: staff` | 403 |
| `/admin/export` staff | 200 |
| `/files?user=bob` с alice | 403 |
| `/files?path=../bob/receipt.txt` с alice | 400 |
| `/debug/logs` с alice | 403 |
| `/debug/logs` со staff | 200, `leaks_token=false`, `leaks_password=false`, значения `<redacted>` |
| `POST /orders` `price=1` с alice | 201, `price=1500` |
| XSS-отзыв и `/reviews/view` | 201/200, `escaped=true` |
| `/assistant/context?order_id=1` с alice | 200, только chair |
| `/assistant/context?order_id=2` с alice | 404 |
| `/assistant/context?order_id=0 OR 1=1` с alice | 400 |

## Тесты

- До фикса: `python3 -m unittest -v test_security` — 25 tests, `FAILED (failures=25, errors=1)`, см. [`test_security_before_fix.txt`](test_security_before_fix.txt).
- После фикса: `make -C practices/practice_06 test` — 41 test, `OK`, см. [`test_security_after_fix.txt`](test_security_after_fix.txt).

## Ограничения

- `delete_tree` оставлен staff как разрешённое действие; клиенту он недоступен.
- Токены сессий не имеют TTL/ротации; для учебного стенда это остаточный риск, не влияющий на проверенные атаки.
- `/debug/logs` остаётся включённым для staff; записи редактируются при сохранении, но содержат метаданные запросов.
