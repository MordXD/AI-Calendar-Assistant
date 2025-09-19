### Что это

Ассистент календаря с SGR‑петлей: LLM генерирует события по строгой Pydantic‑схеме → авто‑валидация/ремонт → принятие решения → запись в Google Calendar.

### Команды

```bash
poetry install  
cp .env.example .env
poetry run uvicorn app.main:app --reload
# или
docker compose up --build
```

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

* Для быстрого старта используется **DRY‑RUN** режим, если нет ключей Google. В логи пишутся операции.
* Для реальной записи подключите `google-api-python-client` и заполните `GOOGLE_CREDS_JSON` или OAuth‑параметры.

### SGR Политики ремонта (baseline)

* Заполнить `timezone`, если отсутствует.
* Если `end <= start` → прибавить дефолтную длительность (например, 30–60 мин) — можно расширить.
* Проверка пересечений (через `list_between`) и авто‑сдвиг ближайшего свободного слота (TODO‑hook).

