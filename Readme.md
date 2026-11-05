# Лабораторная работа №3
## Контейнеризация микросервисного приложения, SQL-хранилище и Docker Compose
### Дисциплина: «Микросервисная архитектура»

## Вариант
**Вариант 5. Отправления (`shipments`).**
Frontend: список отправлений, создание отправления, предметная команда «отправить» (`created → in_transit`).

**Цель работы:** освоить контейнеризацию backend/frontend, подключить PostgreSQL, собрать единый стек через Docker Compose, сохранить REST-контракт ЛР №2 и обеспечить единственную внешнюю точку входа через Nginx на `http://localhost:8080`.

## 1. Целевая архитектура

| Контейнер | Роль | Сети | Порт хоста |
|---|---|---|---|
| `proxy` | Nginx: единая точка входа | `edge` | `8080:80` |
| `frontend` | Статический HTML/CSS/JS | `edge` | нет |
| `backend` | FastAPI + SQLAlchemy + PostgreSQL | `edge`, `data` | нет |
| `db` | PostgreSQL + именованный том | `data` | нет |

Схема запросов:

```text
Браузер → proxy:80 → /        → frontend:80
Браузер → proxy:80 → /api/*   → backend:8000/*
backend → db:5432             → SQL-запросы
```

Ограничения:
- в финальном состоянии `docker compose ps` показывает ровно 4 долгоживущих контейнера;
- `frontend` не содержит `http://localhost:8000`, все запросы идут на относительный `/api/...`;
- `backend` не хранит рабочие данные в глобальном `dict/list`, данные читаются из PostgreSQL;
- `db` не публикует `5432` на хост;
- `proxy` не подключается к сети `data`;
- пароли не хранятся в Dockerfile, исходном коде и образах;
- контейнеры не запускаются в `privileged` и не монтируют Docker socket.

## 2. Структура проекта

```text
project/
  backend/
    main.py
    requirements.txt
    Dockerfile
    .dockerignore
  frontend/
    index.html
    app.js
    styles.css
    Dockerfile
    .dockerignore
  proxy/
    nginx.conf
  compose.yaml
  .env.example
  .gitignore
  README.md
```

## 3. Пошаговая инструкция

### 3.1. Backend: SQLAlchemy + PostgreSQL

Файл `backend/main.py` — пример с сохранением контракта ЛР №2. Замените свой `main.py` или адаптируйте код:

```python
SERVICE_NAME = os.getenv("SERVICE_NAME", "shipment-service")
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "0.1.0")

DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "appdb")
DB_USER = os.getenv("DB_USER", "appuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "change_me")

DATABASE_URL = (
    f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

### 3.2. Frontend

`frontend/index.html`

`frontend/app.js`

`frontend/styles.css`

`frontend/Dockerfile`

`frontend/.dockerignore`

### 3.3. Reverse proxy

`proxy/nginx.conf`:

```nginx
server {
    listen 80;
    server_name _;

    location /api/ {
        # Завершающий / удаляет префикс /api/:
        # /api/shipments -> backend:8000/shipments
        proxy_pass http://backend:8000/;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://frontend:80;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3.4. Переменные окружения

`.env.example` — коммитится в репозиторий:

```env
POSTGRES_DB=appdb
POSTGRES_USER=appuser
POSTGRES_PASSWORD=change_me
APP_PORT=8080
```

В Codespaces создайте `.env` на основе примера и замените пароль:

```bash
cp .env.example .env
```

`.gitignore`:

```gitignore
.env
__pycache__/
*.pyc
.venv/
.pytest_cache/
```

### 3.5. Docker Compose

`compose.yaml`:

## 4. Запуск в GitHub Codespaces

1. Откройте репозиторий в Codespaces.
2. Проверьте Docker Compose:

```bash
docker compose version
```

3. Создайте `.env`:

```bash
cp .env.example .env
```

4. Проверьте итоговую конфигурацию:

```bash
docker compose config
```

5. Соберите и запустите:

```bash
docker compose build
docker compose up -d
```

6. Проверьте контейнеры:

```bash
docker compose ps
```

Должно быть ровно 4 контейнера: `db`, `backend`, `frontend`, `proxy`.

7. В Codespaces откройте вкладку **Ports**, найдите порт `8080` и нажмите **Open in Browser**.  
   Внутри терминала Codespace можно проверять через `localhost`:

```bash
curl -i http://localhost:8080/
curl -i http://localhost:8080/api/shipments
```

Если порт `8080` занят, измените `APP_PORT` в `.env`.

## 5. Проверка и приёмочные сценарии

Проверка Nginx и БД:

```bash
docker compose exec proxy nginx -t
docker compose exec db pg_isready -U appuser -d appdb
```

Сквозной сценарий через proxy:

```bash
# 1. Список
curl -i http://localhost:8080/api/shipments

# 2. Создание
curl -i -X POST http://localhost:8080/api/shipments \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"order-100","destination":"Москва, склад 1"}'

# 3. Предметная команда dispatch
# подставьте id из ответа создания
curl -i -X POST http://localhost:8080/api/shipments/<ID>/dispatch
```

В браузере через forwarded URL:
- список отображается;
- создание добавляет запись;
- кнопка «Отправить» меняет `created → in_transit`;
- после успешной операции список обновляется без ручного изменения URL;
- ошибки и пустой список отображаются.

Проверка изоляции:

```bash
docker compose ps
docker inspect lab3-proxy-1 --format '{{json .NetworkSettings.Networks}}'
docker inspect lab3-db-1 --format '{{json .NetworkSettings.Networks}}'
```

Ожидается:
- `proxy` и `frontend` не входят в `data`;
- `db` не входит в `edge`;
- только `proxy` имеет опубликованный порт.

## 6. Доказательство персистентности

1. Создайте отправление через UI или `curl`.
2. Перезапустите backend:

```bash
docker compose restart backend
```

3. Проверьте, что запись осталась:

```bash
curl http://localhost:8080/api/shipments
```

4. Пересоздайте контейнеры без удаления тома:

```bash
docker compose down
docker compose up -d
```

5. Снова проверьте список — данные должны сохраниться.

6. `docker compose down -v` удаляет том. Выполняйте только после фиксации доказательств:

```bash
docker compose down -v
```

## 7. Обнаруженная ошибка и диагностика

**Симптом:** `502 Bad Gateway` или `404` при запросе `/api/shipments`.

**Вероятная причина:** в `proxy/nginx.conf` указан `proxy_pass http://backend:8000;` без завершающего `/`. Тогда backend получает `/api/shipments`, а не `/shipments`.

**Диагностика:**

```bash
docker compose logs --tail=100 proxy
docker compose exec proxy nginx -t
docker compose logs --tail=100 backend
curl -i http://localhost:8080/api/shipments
```

**Исправление:** использовать `proxy_pass http://backend:8000/;` с завершающим `/`, перезапустить proxy:

```bash
docker compose restart proxy
```

Другая частая ошибка — `DB_HOST=localhost` в backend. В контейнере `localhost` указывает на сам backend, поэтому используется `DB_HOST=db`.

## 8. Ответы на контрольные вопросы

1. **Образ и контейнер.** Образ — неизменяемый шаблон со слоями; контейнер — процесс из образа с собственным writable-слоем. Изменяемое состояние контейнера хранится в writable-слое; данные БД выносятся в том.
2. **0.0.0.0 vs 127.0.0.1.** `0.0.0.0` — слушать все интерфейсы контейнера, чтобы запросы из сети Docker доходили. `127.0.0.1` доступен только внутри самого контейнера.
3. **EXPOSE vs ports/-p.** `EXPOSE` документирует порт образа, но не публикует его на хост. `ports` в Compose и `-p` в `docker run` публикуют порт на хост.
4. **Почему `db`, а не `localhost`.** Backend и PostgreSQL находятся в разных контейнерах. В пользовательской bridge-сети имя `db` разрешается через DNS Docker. `localhost` внутри backend — это сам backend.
5. **Пользовательская bridge-сеть.** Даёт DNS-имена контейнеров, изоляцию и предсказуемое взаимодействие по именам сервисов.
6. **Зачем `edge` и `data`.** `edge` — внешний трафик proxy/frontend/backend; `data` — только backend и db. Это уменьшает поверхность доступа: proxy и frontend не видят БД.
7. **Volume vs bind mount.** Именованный volume управляется Docker и не зависит от пути хоста. Bind mount монтирует конкретный путь хоста.
8. **Почему удаление db не удаляет данные.** Данные PostgreSQL лежат в именованном томе `pgdata`, а не в writable-слое контейнера.
9. **Когда применяются POSTGRES_*.** При первой инициализации пустого data directory. Если том уже создан, новые значения не переинициализируют пароль.
10. **Почему `.env` не хранилище секретов.** Это обычный файл с открытым текстом; он удобен локально, но не обеспечивает управление доступом и аудит. Для production нужны secrets.
11. **Завершающий `/` в `proxy_pass`.** Он заменяет совпавшую часть URI: `/api/shipments` → `/shipments`. Без `/` префикс `/api/` сохранился бы.
12. **Same-origin и CORS.** Браузер обращается к тому же origin `http://localhost:8080`, а Nginx проксирует `/api/` на backend. CORS не нужен.
13. **`depends_on` без healthcheck.** Ждёт только создания/запуска контейнера, но не готовности приложения. Поэтому для db нужен `pg_isready`, для backend — healthcheck.
14. **Liveness и readiness.** `/health/live` проверяет, что процесс жив, без БД. `/health/ready` выполняет `SELECT 1` и показывает готовность принимать трафик.
15. **Как доказать, что опубликован только proxy.** `docker compose ps` и `docker inspect` показывают `PublishedPort` только у proxy; `docker port` для backend/db не даёт публикаций.
16. **Что переносится из ручного запуска в Compose.** Флаги `docker run` переходят в поля сервиса: `image/build`, `environment`, `ports`, `volumes`, `networks`, `depends_on`, `healthcheck`, `command`.

## 9. Вывод

В ходе ЛР №3 приложение контейнеризировано и переведено на SQL-хранилище PostgreSQL. REST-контракт ЛР №2 сохранён: URI, методы, DTO, коды ответов и переходы статусов. Backend получает параметры подключения только из окружения, использует SQLAlchemy 2.x и psycopg, реализует `/health/live` и `/health/ready`. Frontend обращается к API только по относительному `/api/...`, Nginx является единственной внешней точкой входа на порту `8080`. Docker Compose описывает четыре сервиса, две сети, именованный том и healthcheck-зависимости. Данные сохраняются после пересоздания контейнеров; ручной запуск и декларативная оркестрация отличаются воспроизводимостью и управляемостью.