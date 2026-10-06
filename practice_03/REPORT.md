# REPORT: Практика 3 — локальная модель (qwen3.5:4b)

## Оборудование и ОС
- ОС: Linux 6.18.33.2-microsoft-standard-WSL2 (WSL2)
- CPU: AMD Ryzen 7 8840HX (12C/24T)
- RAM: 15 GiB (доступно ~13 GiB)
- GPU: NVIDIA GeForce RTX 5070 Laptop, 8 GiB VRAM, драйвер 581.80, CUDA 13.0

## Версии
- Python: 3.14.4
- Ollama: 0.34.4

## Модель и параметры
- Образ: itmo-agent (FROM qwen3.5:4b)
- Квантизация: Q4_K_M
- Контекст: 65536 токенов
- Параметры: temperature 0.2, top_k 20, top_p 0.95, presence_penalty 1.5
- Обоснование выбора 4B: баланс качества и требований к ресурсам; на данном железе модель отвечает уверенно, 64k контекст доступен.

## Конфигурации
- Modelfile.agent: FROM qwen3.5:4b; num_ctx 65536; temperature 0.2
- demo/opencode.json: провайдер Ollama v1; модель "ollama/itmo-agent"; агент `local-guide` с правами read-only (read/glob/grep), системный prompt из repo-system.txt; steps = 10

## Эксперимент baseline vs system (4B)
- baseline (без system): wall ~19.15s, total ~19.14s; ответ склонен к рассуждениям и рекомендациям
- system (с system.txt): wall ~1.77s, total ~1.77s; краткий ответ «В предоставленных материалах нет ответа»
- Вывод: системная подсказка дисциплинирует ответы (не выдумывать) и ускоряет получение краткого вывода.

## Ответы на 5 вопросов (сводка)
- Q1: Верно. Запуск тестов через `make -C lab/demo test` → `python3 -m unittest -v` (см. lab/Makefile и lab/demo/Makefile).
- Q2: Верно. Пустое имя вызывает ValueError("empty name") (service.py, тест test_service.py).
- Q3: Верно. `unsubscribe` отсутствует (ложная предпосылка).
- Q4: Верно. Сведений о CI нет; в репозитории нет конфигураций CI.
- Q5: Верно. Подписки не сохраняются между перезапусками (память процесса, глобальный set).

Артефакты: practices/practice_03/lab/results/q1.txt..q5.txt, summary.txt.

## Ограничения и наблюдения
- Производительность: 4B (Q4_K_M) на 64k контексте работает стабильно; при большем контексте/выходе возможен рост времени ответа.
- Память: на системе доступно ~13 GiB RAM и 8 GiB VRAM; при нехватке VRAM можно перейти на меньшую квантовку/модель (2B/0.8B) или сократить `num_ctx`.
- Если 64k контекст не тянется в вашем окружении: снизить limit.context в demo/opencode.json до 16384/8192, повторить прогоны и отметить это в отчете.
