# AI-Calendar-Assistant — RAG/Agent сервис для автоматизации планирования

AI-Calendar-Assistant — это AI-агент, который превращает запросы пользователя (“перенеси созвон”, “найди окно”, “создай встречу”) в **безопасные и валидируемые действия** над календарём.

Ключевой контур:
**retrieval → контекст → генерация → валидация → применение результата**

Проект ориентирован на прод-использование: гибридный поиск (BM25 + вектора), pgvector в PostgreSQL, микросервисы, стриминг статусов, OAuth2/OIDC через Keycloak, observability (метрики/логи).

---

## Возможности

### Агентные сценарии (MVP+)
- **Find Free Slots**: поиск свободных слотов с ограничениями (после 15:00, не в пятницу, буферы и т.п.)
- **Create Event**: создание события с участниками/локацией/описанием
- **Reschedule Event**: перенос встречи с проверкой конфликтов
- **Cancel Event**: отмена встречи (с безопасными проверками)
- **Summarize Day/Week** (опционально): краткие сводки/планы на день-неделю

### RAG и поиск
- **Hybrid retrieval**:
  - lexical (BM25 через OpenSearch / Elasticsearch)
  - vector (pgvector в PostgreSQL)
  - **score fusion** (нормализация + взвешивание) → итоговый top-K
- **Фильтры retrieval**: user/tenant, диапазон времени, тип документов (events/rules/notes)
- **Graceful degradation**:
  - fallback на lexical-only при деградации векторного поиска/эмбеддингов
  - ограничение K/контекста при таймаутах

### Безопасность и надежность
- **Structured generation**: LLM возвращает **строгий JSON**, который проходит Pydantic-валидацию
- **Строгая валидация**:
  - schema validation (`extra=forbid`)
  - бизнес-правила (таймзоны, конфликты, лимиты, права)
- **Executor слой**: изменения календаря идут только через валидированный план действий
- **Idempotency**: защита от дублей при повторе запросов
- **Audit log**: фиксируется “что изменили, почему, кем”

### UX и интеграции
- **Streaming статусов**: SSE и/или WebSocket (“ищу слоты…”, “валидирую…”, “применяю…”)
- **Несколько LLM провайдеров**: переключение по конфигурации (через единый адаптер)

### Observability
- Метрики (Prometheus): latency по этапам, fallback rate, cache hit rate, ошибки валидации
- Дашборды (Grafana)
- Логи со сквозным `request_id`

---

## Архитектура

### Компоненты
- **api** (FastAPI): оркестратор пайплайна, SSE/WS, валидация, executor, auth middleware
- **retrieval**: hybrid search (BM25 + vector), score fusion, top-K выдача
- **embedding**: батч-векторизация, кэширование, управление временем ответа
- **postgres (pgvector)**: данные и эмбеддинги
- **opensearch**: BM25/lexical индекс
- **redis**: кэш (эмбеддинги/поиск/сессии), throttling/locks (опционально)
- **keycloak**: OAuth2/OIDC, роли, JWT/JWKS
- **prometheus/grafana**: метрики/дашборды

### Поток данных (высокоуровнево)

```

Client
└─> API (SSE/WS)
├─ Auth (Keycloak JWT via JWKS)
├─ Intent/Command routing
├─ Retrieval (hybrid top-K)
│     ├─ OpenSearch (BM25)
│     └─ Postgres+pgvector (vector search)
├─ Context Builder (лимиты/сжатие)
├─ LLM Adapter (structured JSON output)
├─ Validation (Pydantic + бизнес-правила)
├─ Executor (calendar provider API)
└─ Audit Log + Metrics + Logs

````

### Контур агента (подробно)
1) **Intent parsing**: определить тип действия (create/reschedule/find/cancel)
2) **Hybrid retrieval**: достать релевантные события/правила/заметки (top-K)
3) **Context building**: собрать компактный контекст с лимитами
4) **Structured generation**: LLM → JSON-план действий
5) **Validation**: Pydantic + правила + конфликт-чеки
6) **Apply**: безопасное применение через connector
7) **Streaming status**: отправка прогресса клиенту
8) **Audit/metrics/logs**: фиксация результата

---

## Технологический стек

- Python, FastAPI, asyncio
- PostgreSQL + pgvector (HNSW/IVFFlat индексы)
- OpenSearch (BM25)
- Redis (кэш)
- Keycloak (OAuth2/OIDC, JWKS)
- Prometheus + Grafana
- Docker / Docker Compose
- Pydantic для строгих схем

---

## Быстрый старт (локально)

### Требования
- Docker + Docker Compose
- (опционально) Python 3.11+ для локального запуска без докера

### Запуск инфраструктуры
Из папки `infra/`:

```bash
docker compose up -d
````

Проверки:

* API: [http://localhost:8000/health](http://localhost:8000/health)
* Keycloak: [http://localhost:8080](http://localhost:8080)
* OpenSearch: [http://localhost:9200](http://localhost:9200)
* Grafana: [http://localhost:3000](http://localhost:3000)
* Prometheus: [http://localhost:9090](http://localhost:9090)

---

## Конфигурация (env)

### API (services/api)

* `DATABASE_URL` — Postgres DSN
* `RETRIEVAL_URL` — URL retrieval-сервиса
* `EMBEDDING_URL` — URL embedding-сервиса
* `KEYCLOAK_ISSUER` — issuer realm
* `JWKS_URL` — JWKS endpoint
* `REDIS_URL` — Redis DSN
* `LLM_PROVIDER` — выбранный провайдер (например `openai|anthropic|local`)
* `LLM_MODEL` — модель
* `LLM_TIMEOUT_MS` — таймаут LLM

### Retrieval (services/retrieval)

* `DATABASE_URL`
* `OPENSEARCH_URL`
* `REDIS_URL`
* `HYBRID_W_LEX` / `HYBRID_W_VEC` — веса fusion
* `TOP_K_LEX` / `TOP_K_VEC` / `TOP_K_FINAL`

### Embedding (services/embedding)

* `DATABASE_URL`
* `REDIS_URL`
* `EMBEDDING_MODEL`
* `EMBEDDING_DIM`
* `BATCH_SIZE`
* `EMBEDDING_TIMEOUT_MS`

---

## Данные и индексация

### Postgres (pgvector)

Хранит:

* `events` — локальная реплика календаря
* `documents` — текстовые документы для поиска (events/rules/notes)
* `embeddings` — вектора (doc_id, model_version, vector)
* `rules` — ограничения пользователя
* `audit_log` — журнал применённых действий

### OpenSearch (BM25)

Хранит индекс документов для lexical search.
Индекс обновляется при изменении `documents`.

---

## API (примерная поверхность)

### Health

* `GET /health`

### Agent

* `POST /agent/plan` — построить план (без применения)
* `POST /agent/apply` — построить и применить план
* `GET /agent/stream/{request_id}` — SSE поток статусов (если используется SSE)
* `WS /agent/ws` — WebSocket канал (если используется WS)

### Retrieval (внутренний)

* `POST /retrieve/hybrid` — hybrid top-K
* `POST /retrieve/lexical` — BM25
* `POST /retrieve/vector` — pgvector

### Embedding (внутренний)

* `POST /embed` — батч эмбеддингов
* `POST /reembed_missing` — дозаполнить пропущенные эмбеддинги

---

## Тестирование

Структура:

* `tests/unit` — pure unit (fusion, нормализация, схемы, контекст билдер)
* `tests/integration` — Postgres/Redis/OpenSearch/Keycloak (через docker)
* `tests/e2e` — поднять compose и пройти сценарии

### Unit tests (обязательные)

* score normalization (min-max/z-score)
* fusion (объединение списков, веса)
* context builder (лимиты, “сжатие”)
* Pydantic validation (`extra=forbid`, обязательные поля)
* бизнес-валидаторы (конфликты, таймзоны, ограничения)

### Integration tests (обязательные)

* pgvector top-K выдача + фильтры
* OpenSearch BM25 индексация и поиск
* Redis cache hit/miss
* Keycloak: JWKS валидация, отказ без токена, отказ с неверным `aud/iss`

### E2E tests (обязательные)

* сценарий `find_free_slots`
* сценарий `reschedule_event`
* негативный сценарий: LLM вернул невалидный JSON → “ничего не применено”

---

## Observability

### Метрики (Prometheus)

* `agent_request_total`
* `agent_latency_ms{stage=...}`
* `retrieval_latency_ms{type=lex|vec|hybrid}`
* `fallback_total`
* `cache_hit_total`
* `llm_json_validation_error_total`

### Логи

* `request_id` — сквозной идентификатор
* записи по этапам пайплайна
* аудит действий executor

---

## Безопасность

* **OAuth2/OIDC** через Keycloak
* JWT проверка по **JWKS**
* проверка `iss`, `aud`, `exp`
* роли/политики доступа на уровне API
* изоляция данных по `user_id/tenant_id`

---

## Roadmap (идеи развития)

* Больше провайдеров календаря (Google/MS Graph/CalDAV)
* Авто-синхронизация через webhooks/watch
* Reranking (cross-encoder) поверх top-K
* Мультитенантность “из коробки”
* Трассировка (OpenTelemetry) + распределённые трейсы

---


