# 2 Лабораторная работа
#### Сетевое взаимодействие микросервиса:
#### OSI, HTTP/HTTPS и REST API
#### Дисциплина: «Микросервисная архитектура»

## Вариант
![alt text](docs/{78B04859-33EB-4267-8F4F-0D653167A757}.png)

**Цель работы:** Связать теорию уровней OSI, работу HTTP/HTTPS и ограничения REST с наблюдаемым поведением реального API. Научиться проектировать фильтры, частичное изменение ресурса (PATCH), возвращать корректные статусы и заголовки, а также запускать сервис по HTTPS.

## 2. Схема пути запроса
**Клиент → IP/порт → TCP/TLS → HTTP → FastAPI-обработчик**

| Уровень OSI | Компонент | Что видит разработчик |
| :--- | :--- | :--- |
| 7. Прикладной | HTTP, JSON, REST | Метод, URI, код статуса, тело запроса/ответа |
| 6. Представления | TLS | Шифрование канала (HTTPS) |
| 4. Транспортный | TCP | Соединение, порты 8000 (HTTP) и 8443 (HTTPS) |
| 3. Сетевой | IP | Адрес 127.0.0.1 (loopback) |

## 3. Таблица маршрутов

| Метод | URI | Входные данные | Успешный статус | Ошибки |
| :--- | :--- | :--- | :--- | :--- |
| GET | `/health` | — | 200 OK | — |
| GET | `/shipments` | Query: `status`, `order_id` | 200 OK | 422 (невалидный status) |
| GET | `/shipments/{id}` | Path: `id` | 200 OK | 404 Not Found |
| POST | `/shipments` | JSON: `order_id`, `destination` | 201 Created + `Location` | 418 Conflict (дубликат `order_id`), 422 |
| POST | `/shipments/{id}/dispatch` | Path: `id` | 200 OK | 404, 409 (неверное состояние) |
| PATCH | `/shipments/{id}` | JSON: `status` | 200 OK | 400, 404, 409 |

## 4. Реализация ключевых механизмов

### 4.1. Query-фильтры (GET /shipments)
Реализована фильтрация по статусу (`status`) и номеру заказа (`order_id`). Параметры опциональны, что позволяет комбинировать их.

```python
@app.get("/shipments", response_model=list[Shipment])
def list_shipments(
    status: Annotated[ShipmentStatus | None, Query()] = None,
    order_id: Annotated[str | None, Query()] = None,
) -> list[Shipment]:
    shipments = list(store.values())
    if status is not None:
        shipments = [s for s in shipments if s.status == status]
    if order_id is not None:
        shipments = [s for s in shipments if s.order_id == order_id]
    return shipments
```

### 4.2. Частичное изменение (PATCH)
Метод `PATCH /shipments/{id}` позволяет изменить статус отправления. Согласно варианту, изменение разрешено **только** если текущий статус — `created`. Если тело пустое, возвращается 400. Если статус не `created`, возвращается 409.

```python
@app.patch("/shipments/{shipment_id}", response_model=Shipment)
def patch_shipment(shipment_id: str, payload: ShipmentPatch) -> Shipment:
    shipment = store.get(shipment_id)
    if shipment is None:
        raise HTTPException(404, "Shipment not found")
    if shipment.status != "created":
        raise HTTPException(409, "Only shipments in 'created' status can be edited")
    
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(400, "At least one field is required")
        
    updated = shipment.model_copy(update=changes)
    store[shipment_id] = updated
    return updated
```

### 4.3. Диагностические заголовки (Middleware)
Middleware перехватывает все запросы, добавляет `X-Request-ID` (из запроса или сгенерированный) и вычисляет время обработки `X-Process-Time-ms`.

```python
@app.middleware("http")
async def add_diagnostic_headers(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    started = perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-ms"] = f"{(perf_counter() - started) * 1000:.2f}"
    return response
```

### 4.4. Создание ресурса с Location (POST /shipments)
При успешном создании возвращается 201 и заголовок `Location`, указывающий на URI нового ресурса. *Примечание: в вашем коде необходимо добавить параметр `response: Response` в функцию `create_shipment`, иначе код вызовет ошибку. Также рекомендуется заменить код 418 на 409 для соответствия стандартам.*

```python
@app.post("/shipments", response_model=Shipment, status_code=status.HTTP_201_CREATED)
def create_shipment(payload: ShipmentCreate, response: Response) -> Shipment:
    for shape in store.values():
        if shape.order_id == payload.order_id:
            raise HTTPException(status_code=418, detail="Order_id is already created")
    
    shipmentCreate = Shipment(
        id=str(uuid4()),
        order_id=payload.order_id,
        destination=payload.destination,
        status='created'
    )
    store[shipmentCreate.id] = shipmentCreate
    response.headers["Location"] = f"/shipments/{shipmentCreate.id}"
    return shipmentCreate
```

## 5. Тестирование


## 6. HTTPS и TLS termination
Для запуска по HTTPS сгенерирован самоподписанный сертификат:
```bash
>> mkdir -p certs

>> openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
 -keyout certs/dev-key.pem -out certs/dev-cert.pem \
 -subj "/CN=localhost" \
 -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

>> chmod 600 certs/dev-key.pem
```
Сервис запущен с флагами `--ssl-keyfile` и `--ssl-certfile` на порту 8443. Проверка осуществляется командой `curl -k -v https://127.0.0.1:8443/docs`. Флаг `-k` используется только для учебного самоподписанного сертификата.

## 7. Ответы на контрольные вопросы

1. **Уровни OSI:** HTTP — прикладной (7), TLS — представления (6), TCP — транспортный (4), IP — сетевой (3).
2. **URI, IP, порт:** URI идентифицирует ресурс, IP — узел в сети, порт — конкретный процесс на узле.
3. **HTTP-сообщение:** Запрос состоит из метода, URI, версии, заголовков и тела. Ответ — из кода статуса, заголовков и тела.
4. **GET vs POST:** GET безопасен (не меняет состояние) и идемпотентен (повторные вызовы дают тот же результат). POST создает ресурсы и обычно не идемпотентен.
5. **Коды 400, 404, 409, 422:** 400 — противоречивые параметры; 404 — ресурс не найден; 409 — конфликт с текущим состоянием; 422 — ошибка валидации Pydantic.
6. **Location в 201:** Указывает клиенту URI только что созданного ресурса (принцип REST).
7. **PATCH vs PUT:** PATCH изменяет только переданные поля, PUT заменяет ресурс целиком.
8. **Stateful vs Stateless:** Статус `created` хранится в ресурсе (в БД/памяти), а не в сессии клиента, поэтому REST остается stateless.
9. **TLS:** Защищает от прослушивания и подмены (конфиденциальность, целостность, аутентификация сервера). Не защищает от ошибок в бизнес-логике приложения.
10. **curl -k:** Отключает проверку сертификата, что делает соединение уязвимым для MITM-атак. Недопустимо в production.
11. **OpenAPI:** FastAPI генерирует спецификацию из Pydantic-моделей и декораторов. Swagger UI визуализирует её.
12. **X-Request-ID:** Позволяет отследить путь одного запроса через логи нескольких микросервисов.
13. **TLS Termination:** Passthrough — на бэкенде; Edge — на прокси (Nginx); Bridging — на прокси и бэкенде.
14. **X-Forwarded-*:** Клиент может подделать эти заголовки. Доверять им можно только от известного reverse proxy.
15. **HTTP между Nginx и FastAPI:** Допустим на localhost или в изолированной доверенной сети. В остальных случаях требуется повторное шифрование (TLS bridging).

## 8. Вывод
В ходе Лабораторной работы №2 был расширен функционал сервиса отправлений. Реализованы query-фильтры для коллекции, частичное изменение ресурса через PATCH и корректная обработка создания ресурса с заголовком `Location`. 

Сервис успешно запущен по HTTPS с использованием самоподписанного сертификата. Написаны и пройдены автотесты, подтверждающие соблюдение HTTP-контракта.