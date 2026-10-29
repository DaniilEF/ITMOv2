# Evidence — практика 6

## Стенд

- Сервис: `practices/practice_06/lab/service.py`
- Адрес: `http://127.0.0.1:8066`
- Порт: `8066`
- PID: см. `/tmp/practice06-service.pid`
- Лог запуска: `/tmp/practice06-service.log`
- Fixture root: пересоздаётся при каждом запуске, актуальный путь — в логе
- Перезапуск: `cd practices/practice_06/lab && python3 service.py --port 8066`
- Остановка: `kill $(cat /tmp/practice06-service.pid)`

## Тесты на исходном коде

```
make -C practices/practice_06 install
make -C practices/practice_06 test
Ran 16 tests ... OK
```

## Каталоги

- `before/` — атаки и ответы до исправлений.
- `after/` — повторные атаки после исправлений.
- `llm/` — входы/выходы `shop-planner` и `threat-judge`.

## Воспроизведение атак

```bash
python3 practices/practice_06/evidence/before/run_attacks.py
python3 practices/practice_06/evidence/after/run_attacks.py
python3 practices/practice_06/evidence/after/run_forced_decisions.py
python3 practices/practice_06/evidence/after/run_auth_checks.py
```

Скрипт пишет `before/<id>.json` и `before/SUMMARY.md`. В конце он вызывает
`delete_tree(".")`, проверяет ущерб и перезапускает сервер по PID из
`/tmp/practice06-service.pid`, чтобы восстановить фикстуры. Перед запуском
сервер должен быть поднят на `127.0.0.1:8066`.

Токены и пароли в evidence заменены на `<token>`/`<password>`; секрет
`TEST_ONLY_OPERATOR_SECRET` оставлен как доказательство чтения приватного файла.

## После фикса

- `service.py` SHA-256: `6222c0012a4bac47c8b8a0f2aac57fe660c458a41cb25afb35a61104f0234e40`
- `sandbox.py` не изменён: `dcd6b6630d3dec67e7185c1017e4999a3faa5998ff091419dade31b64132ddcf`
- `after/test_security_before_fix.txt` — падения security-тестов на исходном коде.
- `after/test_security_after_fix.txt` — `make step6` и `make test` после фикса (41 тест, OK).
- `after/28-auth-checks.json` — аутентифицированные проверки; `20..27` — принудительные решения executor.
- `llm/after/COMPARE.md` — повторный запуск `shop-planner` после фикса.
