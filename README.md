### Что это

Ассистент календаря с SGR‑петлей: Structured Generation (LLM → строгое Pydantic‑JSON) → авто‑валидация/ремонт → принятие решения → запись в Google Calendar.

### Команды

```bash
poetry install
cp .env.example .env
poetry run uvicorn app.main:app --reload
# или
docker compose up --build
```

### Бенчмарки

```bash
python -m benchmarks.sgr_bench
```

### Конфигурация

Основные переменные окружения:

* `LLM_PROVIDER` — `openai` (по умолчанию) или `openrouter`.
* `OPENAI_API_HOST` — кастомный хост OpenAI API (для self-hosted совместимых шлюзов).
* `OPENROUTER_API_KEY` / `OPENROUTER_API_HOST` — ключ и хост OpenRouter; можно также использовать `OPENAI_API_KEY`.
* `SQLITE_DB_PATH` — путь к локальной базе для кеша Google Calendar и токенов OAuth.
* `GOOGLE_CREDS_JSON` / `GOOGLE_TOKEN_JSON` — JSON клиента/токена или путь к файлу.
* `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` — параметры OAuth, если нет готового JSON.

### Эндпойнты

* `POST /events/suggest`: { instruction, now?, timezone? } → список кандидат‑событий + trace\_id
* `POST /events/sync`: CommitPlan → CommitResult (created/updated/skipped)
* `GET /health`: ping

### Пример запроса

```bash
curl -X POST http://localhost:8000/events/suggest \
  -H 'Content-Type: application/json' \
  -d '{"instruction":"Спланируй 2 часа Deep Work завтра утром и встречу с Даней в пятницу 15:00"}'
```

### Заметки по Google Calendar

* Клиент автоматически использует SQLite (`SQLITE_DB_PATH`) для хранения токенов и локального кеша событий.
* При отсутствии учётных данных клиент остаётся в **DRY‑RUN** режиме, но операции всё равно логируются и пишутся в SQLite.
* Для интерактивного OAuth потока выполните `python -m app.services.google_calendar --authorize` и следуйте инструкциям в браузере.
* Для реальной записи заполните `GOOGLE_CREDS_JSON`/`GOOGLE_TOKEN_JSON` или выдайте `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`.
* Список кешированных событий можно посмотреть через `python -m app.services.google_calendar --list`.

### SGR Политики ремонта (baseline)

* Заполнить `timezone`, если отсутствует.
* Если `end <= start` → прибавить дефолтную длительность (например, 30–60 мин) — можно расширить.
* Проверка пересечений (через `list_between`) и авто‑сдвиг ближайшего свободного слота (TODO‑hook).

