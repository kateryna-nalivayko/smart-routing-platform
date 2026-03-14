# 🌿 One Big Green (OBG) — Smart Routing Platform

**One Big Green (OBG)** — це інтелектуальна платформа для управління професійним обслуговуванням рослин (interiorscaping). 

### 🎯 Проблема та мета
Суть бізнесу полягає в тому, що технічні спеціалісти відвідують офіси клієнтів для догляду за рослинами (полив, підживлення, лікування). Основна задача платформи — **автоматизувати хаос**: перетворити сотні розрізнених замовлень на чіткі, ефективні та повторювані маршрути.

**Мета проєкту:**
* Мінімізувати витрати на пальне та час у дорозі.
* Суворо дотримуватись графіків клієнтів та часових вікон доступу.
* Враховувати специфічні навички персоналу (skills) та допуски безпеки.
* Створювати стабільні графіки на тижні вперед (циклічність).

---

## 🏗️ 1. Загальна архітектура (System Architecture)

Система побудована на базі асинхронної сервісної архітектури для забезпечення стабільної роботи при складних математичних обчисленнях.

![System Architecture](docs/architecture/01-system-architecture.png)

> 📂 *Вихідний код: [01-system-architecture.puml](docs/architecture/01-system-architecture.puml)*

**Ключові компоненти:**
* **FastAPI**: Приймає дані, взаємодіє з **AWS Location Service** для геокодингу адрес.
* **Dramatiq + RabbitMQ**: Брокер та воркер для фонового виконання алгоритмів оптимізації.
* **Google OR-Tools**: Математичне ядро для вирішення задачі маршрутизації (VRP).
* **PostgreSQL + PostGIS**: Зберігання геоданих та JSONB-структур об'єктів.

---

## 🔄 2. Послідовність роботи та Логіка (Sequence Diagram)

Алгоритм балансує між **жорсткими обмеженнями** (вікна доступу, навички, ліміти годин) та **м'якими обмеженнями** (економія пального, лояльність клієнта до конкретного техніка).

![Sequence Diagram](docs/architecture/02-sequence.png)

> 📂 *Вихідний код: [02-sequence.puml](docs/architecture/02-sequence.png)*

### 🧠 Особливості алгоритму:
* **Циклічність:** Залежно від частоти візитів (2, 3 або 4 тижні), система розраховує спільний цикл (наприклад, 12 тижнів), який потім автоматично клонується в календарі.
* **Мультимодальність та Хаби:** У щільних районах алгоритм будує ланцюжки: *авто -> паркувальний хаб -> піший обхід кількох офісів -> повернення до авто*.
* **Пріоритезація:** 1. Фільтрація за навичками та допусками.
    2. Перевірка часових вікон.
    3. Врахування побажань клієнта щодо техніка.
    4. Географічна оптимізація.

---

## 📊 3. Структура даних (ER-Diagram)

Модель даних зосереджена на двох сутностях: **Локація (Service Site)** та **Технік (Technician)**. Ми використовуємо гібридний підхід: реляційні зв'язки для стабільних даних та `JSONB` для гнучких описів (наприклад, списки рослин `displays`).

![ER Diagram](docs/architecture/03-db-er.png)

> 📂 *Вихідний код: [03-db-er.puml](docs/architecture/03-db-er.puml)*

**Складні обмеження в моделі:**
* **Security Permits:** Перевірка допусків техніка до режимних об'єктів.
* **Skill Matching:** Рівень кваліфікації (Junior/Senior), робота з "зеленими стінами", висотні роботи.
* **Physically Demanding:** Врахування фізичної складності локації відповідно до можливостей техніка.

---

## 🚀 Технологічний стек
* **Backend:** FastAPI (Python 3.14+)
* **Database:** PostgreSQL 18 + PostGIS
* **ORM:** SQLAlchemy 2.0 (Async) + GeoAlchemy2
* **Task Queue:** Dramatiq + RabbitMQ
* **Optimization:** Google OR-Tools
* **Cloud Services:** AWS Location Service (Geocoding)

## 📁 Документація
Усі схеми та вихідні коди PlantUML знаходяться в директорії: `docs/architecture/`
- Детальний опис фактичних констрейнтів та роботи OR-Tools: `docs/constraints.md`
---

## How to run

### 1. Prerequisites
- Python `3.14.x`
- `uv` (Astral) для керування залежностями
- PostgreSQL `18+` (локально або через Docker)
- Docker + Docker Compose (рекомендовано для швидкого старту)
- RabbitMQ: **не обов'язково для поточного MVP**, бо оптимізація зараз виконується синхронно в API-процесі

### 2. Environment variables
Створіть `.env` на основі `.env.example`.

Мінімально потрібні для локального запуску:
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `DB_HOST`
- `DB_PORT`

Опційні (для майбутнього async/infra-режиму):
- `RABBITMQ_URL`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_DEFAULT_REGION`

### 3. Setup

```bash
# 1) встановити залежності
uv sync

# 2) підняти PostgreSQL (варіант через Docker)
docker compose up -d postgres

# 3) застосувати міграції
uv run alembic upgrade head
```

### 4. Execution

#### Варіант A: запуск API (поточний MVP)

```bash
uv run uvicorn app.entrypoints.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI:
- `http://localhost:8000/docs`

#### Варіант B: запуск через Docker Compose

```bash
docker compose up --build app postgres
```

#### Воркер (Dramatiq)
У поточній MVP-конфігурації оптимізація виконується синхронно у FastAPI handler, тому окремий Dramatiq worker зараз не є обов'язковим для тестування алгоритму.

Коли async-контур увімкнений, запуск воркера буде окремою командою на кшталт:

```bash
uv run dramatiq app.entrypoints.api.workers.optimize_worker
```

### 5. Input/Output example

#### Створення задачі оптимізації

```bash
curl -X POST "http://localhost:8000/api/v1/optimize" \
  -H "Content-Type: application/json" \
  -d '{
    "target_date": "2026-02-26",
    "timeout_seconds": 30
  }'
```

Приклад відповіді:

```json
{
  "task_id": "c3c53b77-e267-4b0b-a2d7-06041a6dd9cb",
  "status": "queued",
  "message": "Task queued. Use GET /tasks/c3c53b77-e267-4b0b-a2d7-06041a6dd9cb to check status"
}
```

#### Перевірка статусу

```bash
curl "http://localhost:8000/api/v1/tasks/c3c53b77-e267-4b0b-a2d7-06041a6dd9cb"
```

Приклад відповіді:

```json
{
  "task_id": "c3c53b77-e267-4b0b-a2d7-06041a6dd9cb",
  "status": "success",
  "target_date": "2026-02-26",
  "routes_created": 25,
  "sites_unassigned": 150,
  "total_distance_km": null,
  "error_message": null,
  "created_at": "2026-03-06T10:31:50.885934Z",
  "started_at": null,
  "completed_at": null
}
```

### 6. Test data
В репозиторії вже є тестові дані:
- `data/Routing_pilot_data_input_FINAL.xlsx`

Оптимізатор у поточному MVP читає саме `Routing_pilot_data_input_FINAL.xlsx`.

### 7. Зручний перегляд побудованих маршрутів

Після створення задачі через `POST /api/v1/optimize` можна отримати детальну розкладку:

```bash
curl "http://localhost:8000/api/v1/tasks/<task_id>/routes"
```

Що повертає endpoint:
- маршрути по даті задачі;
- техніка, порядок зупинок, часи прибуття/виїзду;
- `site_code`/`site_name` для кожної зупинки;
- метрики маршруту (`stops_count`, `total_duration_minutes`, `total_travel_time_minutes`).

Додаткові endpoints:
- `GET /api/v1/tasks` — список останніх задач оптимізації;
- `GET /api/v1/routes?target_date=YYYY-MM-DD` — список маршрутів із фільтром по даті.
- `GET /api/v1/tasks/<task_id>/schedule-log` — JSON-лог активностей у форматі `date/day_of_week/start_time/end_time/technician_name/location_name/location_to/activity_type`;
- `GET /api/v1/tasks/<task_id>/constraints` — що з констрейнтів враховано, а що ще ні;
- `GET /api/v1/tasks/<task_id>/artifacts` — шляхи до згенерованих `schedule_log.json`, `schedule_log.xlsx`, `constraints_summary.json`.

Артефакти також записуються на диск у:
- `data/output/<task_id>/schedule_log.json`
- `data/output/<task_id>/schedule_log.xlsx`
- `data/output/<task_id>/constraints_summary.json`

### 8. Seed даних з Excel

Скрипт для наповнення БД:

```bash
# перевірити Excel без запису у БД
uv run python scripts/seed_from_excel.py --dry-run

# повне наповнення (очистити існуючі техніки/сайти/маршрути та завантажити заново)
uv run python scripts/seed_from_excel.py --truncate

# вказати інший файл
uv run python scripts/seed_from_excel.py --excel data/Routing_pilot_data_input_FINAL.xlsx --truncate
```

Скрипт переносимий: після клону на іншому ПК достатньо підняти PostgreSQL, виконати міграції та запустити seed-команду вище.

### 8.1. Підготовка geocoding cache

Оптимізатор більше не використовує жорсткі `15 хв / 5 км / 50 км / 300 хв` заглушки. Для побудови travel-time matrix потрібні реальні координати адрес.

Варіанти:
- заповнити `data/geocoding_cache.json` власними координатами;
- або одноразово прогріти cache через Nominatim:

```bash
SMART_ROUTING_GEOCODER=nominatim uv run python scripts/build_geocoding_cache.py
```

Якщо в cache відсутні координати, оптимізація завершиться помилкою з переліком проблемних адрес, а не побудує фіктивний VRP-результат.

### 8.2. Які констрейнти зараз враховуються

Нижче наведено фактичний стан поточного MVP, а не цільову архітектурну ідею.

#### Враховуються

- **Часові вікна локацій**
  Реалізація: `app/adapters/optimization/or_tools_solver.py`
  Як саме: для кожного візиту в `Time` dimension задається `SetRange(tw_from, tw_to)`.

- **Тривалість робіт на локації**
  Реалізація: `app/adapters/optimization/or_tools_solver.py`
  Як саме: `service_min` додається в transit callback, тобто візит займає реальний час у моделі.

- **Час на дорогу між точками**
  Реалізація: `app/adapters/optimization/travel_metrics.py`, `app/adapters/geocoding.py`, `app/adapters/optimization/solver_adapter.py`
  Як саме: адреси переводяться в координати, відстань рахується через Haversine, час у дорозі оцінюється через середню швидкість.

- **Навички та capability-обмеження техніків**
  Реалізація: `app/adapters/optimization/or_tools_solver.py`
  Як саме: `_eligible_vehicle_ids()` відсікає техніків без потрібного skill level, а також без допуску до фізичних/висотних/ліфтових/пестицидних/громадянських вимог.

- **Permit-обмеження**
  Реалізація: `app/adapters/optimization/excel_oasis_loader.py`, `app/adapters/optimization/oasis_week_builder.py`, `app/adapters/optimization/or_tools_solver.py`
  Як саме: якщо `Permit required = yes`, у допустимих кандидатах залишаються лише техніки з колонки `Techs with permit`.

- **Обмеження по робочому дню техніка**
  Реалізація: `app/adapters/optimization/or_tools_solver.py`
  Як саме: враховуються `shift_from`, `shift_to`, а також `max_work_min_today`.

- **Візити, де потрібно кілька техніків одночасно**
  Реалізація: `app/adapters/optimization/oasis_week_builder.py`, `app/adapters/optimization/or_tools_solver.py`
  Як саме: для таких локацій створюється група копій візиту з одним `group_id`, а solver примушує їх стартувати одночасно на різних машинах.

#### Враховуються частково

- **Preferred / avoid technicians**
  Реалізація: `app/adapters/optimization/or_tools_solver.py`
  Поточна логіка: `avoid` працює як жорстке виключення, а `preferred` зараз поводиться як allow-list, тобто якщо preferred список заданий, інші техніки не розглядаються. Це сильніше, ніж класичний soft-constraint.

- **Частота повторних візитів протягом тижня**
  Реалізація: `app/adapters/optimization/oasis_week_builder.py`
  Поточна логіка: builder розкладає `1x..5x` по фіксованих day-pattern, але немає універсального hard-rule на кшталт «два візити не можуть стояти день за днем» для всіх кейсів.

#### Поки не враховуються

- **Перерва техніка**
  Дані парсяться з Excel, але в solver окремий break interval не вставляється.
  Файли: `app/adapters/optimization/excel_oasis_loader.py`, `app/adapters/optimization/or_tools_solver.py`

- **Максимум годин на тиждень**
  Дані зчитуються, але обмеження не контролюється на рівні всієї тижневої оптимізації.
  Файли: `app/adapters/optimization/excel_oasis_loader.py`, `app/adapters/optimization/oasis_week_builder.py`

- **Старт/фініш з дому**
  У поточному MVP маршрути будуються від `office` до `office`.
  Файли: `app/adapters/optimization/oasis_week_builder.py`

- **Мультимодальність `drive to hub and then walk`**
  Опція є в даних, але окремого математичного режиму для parking hub + walking cluster поки немає.

- **Багатотижневий цикл 2/3/4 тижні**
  Поточний оптимізатор планує один робочий тиждень, без LCM-циклів на 12 тижнів.

### 8.3. Формат вихідного JSON-логу

Після успішної оптимізації формується файл:
- `data/output/<task_id>/schedule_log.json`

Щоб згенерувати артефакти напряму з Excel без запуску API, можна використати:

```bash
uv run python scripts/generate_schedule_artifacts.py --week-start 2026-03-16
```

Кожен запис має формат:

```json
{
  "date": "2026-03-16",
  "day_of_week": "Monday",
  "start_time": "08:00",
  "end_time": "08:25",
  "technician_name": "Luis Miguel",
  "location_name": "Office",
  "location_to": "KY-001-INT",
  "activity_type": "Commute"
}
```

Типи `activity_type`, які зараз повертаються:
- `Commute`
- `Interior`
- `Exterior`
- `Floral`
- `Service`

### 8.4. Де дивитися результат

- API-лог: `GET /api/v1/tasks/<task_id>/schedule-log`
- Excel-таблиця: `data/output/<task_id>/schedule_log.xlsx`
- Зведення по констрейнтах: `GET /api/v1/tasks/<task_id>/constraints`
- Шляхи до артефактів: `GET /api/v1/tasks/<task_id>/artifacts`


### 9. Explain endpoint (чому є unassigned)

Для швидкої аналітики причин невключених візитів:

```bash
curl "http://localhost:8000/api/v1/tasks/<task_id>/explain"
```

Endpoint повертає:
- `total_requested_visits`
- `assigned_estimate`
- `unassigned_count`
- bucket-розбивку причин:
  - `no_eligible_technician`
  - `overflow_guard_limit`
  - `optimizer_or_capacity`

Це зручно для демо та первинної діагностики якості плану.
