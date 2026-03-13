# Docube — Recommendation Service

Microservice gợi ý tài liệu học thuật trong hệ thống **Docube** — nền tảng quản lý và chia sẻ tài liệu đại học Việt Nam. Service hoạt động hoàn toàn hướng sự kiện: nhận dữ liệu qua Kafka, tự xây dựng mô hình người dùng theo thời gian thực, và trả gợi ý cá nhân hóa qua REST API.

---

## Mục lục

1. [Vị trí trong hệ thống](#vị-trí-trong-hệ-thống)
2. [Kiến trúc nội bộ](#kiến-trúc-nội-bộ)
3. [Luồng dữ liệu & Embedding](#luồng-dữ-liệu--embedding)
4. [Kafka Event Contracts](#kafka-event-contracts)
5. [REST API](#rest-api)
6. [Cấu trúc thư mục](#cấu-trúc-thư-mục)
7. [Môi trường & Cấu hình](#môi-trường--cấu-hình)
8. [Kết nối với các service khác](#kết-nối-với-các-service-khác)

---

## Vị trí trong hệ thống

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          Hệ thống Docube                                 │
│                                                                          │
│  ┌─────────────────┐    document-events    ┌──────────────────────────┐  │
│  │ Document Service│ ──────────────────►   │                          │  │
│  └─────────────────┘                       │   Recommendation         │  │
│                                            │   Service                │  │
│  ┌─────────────────┐    user-events         │                          │  │
│  │  User Service   │ ──────────────────►   │  ┌──────────────────┐   │  │
│  └─────────────────┘                       │  │ PostgreSQL        │   │  │
│                                            │  │ + pgvector       │   │  │
│  ┌─────────────────┐  recommendation-events │  └──────────────────┘   │  │
│  │  Interaction /  │ ──────────────────►   │  ┌──────────────────┐   │  │
│  │  Payment Svc    │                       │  │ Redis Cache      │   │  │
│  └─────────────────┘                       │  └──────────────────┘   │  │
│                                            └──────────┬───────────────┘  │
│  ┌─────────────────┐      REST API                    │                  │
│  │  API Gateway /  │ ◄────────────────────────────────┘                  │
│  │  Frontend       │   GET /recommendations                              │
│  └─────────────────┘                                                     │
│                                                                          │
│  ┌─────────────────┐                                                     │
│  │  Eureka Server  │ ◄──── service discovery (đăng ký tự động)           │
│  └─────────────────┘                                                     │
└──────────────────────────────────────────────────────────────────────────┘
```

**Nguyên tắc thiết kế:**
- Service này **không chủ động gọi** sang Document/User/Interaction service
- Mọi dữ liệu đầu vào đến qua **Kafka (push model)**
- Đầu ra duy nhất là **REST API** `/recommendations` — các service khác polling hoặc Gateway proxy lại cho client
- Không cần shared database với bất kỳ service nào khác

---

## Kiến trúc nội bộ

```
                    Kafka Topics
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
  document-events   user-events  recommendation-events
          │              │              │
  DocumentConsumer  UserConsumer  InteractionConsumer
          │              │              │
     encode_doc()   encode_user()  process_interaction()
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  PostgreSQL + pgvector
                  (documents, users_profile,
                   user_interactions, search_history)
                         │
                         ▼
              GET /recommendations?user_id=X
                         │
                  ┌──────┴──────┐
                  ▼             ▼
            Redis Cache?    ANN Search (pgvector)
            HIT → return    MISS → score → rerank
                                     │
                                     ▼
                              Redis Cache (TTL 300s)
                                     │
                                     ▼
                              JSON Response
```

**Stack:**

| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| API Framework | FastAPI (Python 3.12) | async, uvicorn |
| Embedding Model | sentence-transformers `all-MiniLM-L6-v2` | EMBEDDING_DIM = 384 |
| Vector Store | PostgreSQL 16 + pgvector | IVFFLAT index, lists=100, probes=10 |
| Cache | Redis 7 | TTL = 300s, key = `rec:{user_id}` |
| Message Bus | Apache Kafka (Confluent) | 3 topics, PLAINTEXT hoặc SASL |
| ML Re-ranker | LightGBM (fallback: LogisticRegression) | train offline, load từ file pkl |
| Service Discovery | Spring Cloud Netflix Eureka | tự đăng ký khi startup |
| DB Driver | asyncpg | async, connection pool |

---

## Luồng dữ liệu & Embedding

### Tổng quan embedding

Mỗi tài liệu và mỗi người dùng được đại diện bởi một **vector 384 chiều** trong không gian ngữ nghĩa. Gợi ý hoạt động bằng cách tìm tài liệu có vector gần nhất với vector của người dùng.

```
Tài liệu:  [title + description + tags + faculty + author] ──encode──► vector_doc (384d)
Người dùng: [role + faculty + interests]                   ──encode──► vector_user (384d)

Gợi ý:  cosine_distance(vector_user, vector_doc) → top-K gần nhất
```

### Embedding drift theo thời gian

Vector người dùng **không cố định** — nó thay đổi mỗi khi người dùng có hành động mới:

```
Khi user tương tác với tài liệu D:
  new_embedding = old_embedding * (1 - weight) + embedding(D) * weight
  new_embedding = normalize(new_embedding)

Khi user search query Q:
  new_embedding = old_embedding * (1 - 0.1) + encode(Q) * 0.1
               + avg_embedding(docs_matching_keywords(Q)) * 0.15
```

**Trọng số blend theo loại tương tác:**

```
┌─────────────┬────────────────┬──────────────────┬─────────────────────────────────┐
│ interaction │ embedding weight│ popularity +     │ Ý nghĩa                         │
├─────────────┼────────────────┼──────────────────┼─────────────────────────────────┤
│ buy         │ 1.0            │ +10.0            │ Giao dịch thực — tín hiệu mạnh  │
│ bookmark    │ 0.6            │ +5.0             │ Lưu lại để đọc sau              │
│ download    │ 0.4            │ +3.0             │ Tải về, có ý định dùng          │
│ read        │ 0.2            │ +1.0             │ Mở xem description              │
│ view        │ 0.2            │ +1.0             │ Xem qua, không cam kết          │
│ search      │ 0.1 + 0.15     │ —                │ Query text + matching docs      │
└─────────────┴────────────────┴──────────────────┴─────────────────────────────────┘
```

### Pipeline gợi ý chi tiết

```
GET /recommendations?user_id=X
         │
         ▼
┌─────────────────────┐
│  1. Redis Cache?     │──── HIT ────► return (TTL 300s, ~1ms)
└────────┬────────────┘
         │ MISS
         ▼
┌─────────────────────────────┐
│  2. Load user profile        │
│   embedding, role, ab_group  │
└────────┬────────────────────┘
         │
         ├── embedding == NULL? (cold start)
         │         ▼
         │   Có search history?
         │     YES → encode queries gần nhất → ANN search
         │     NO  → get_trending() (sort by popularity DESC)
         │
         ▼ (user có embedding)
┌──────────────────────────────────────┐
│  3. ANN Search — pgvector             │
│   SELECT ... ORDER BY emb <=> $user  │
│   LIMIT 200  (IVFFLAT index)         │
└────────┬─────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  4. Lọc đã tương tác gần đây         │
│   exclusion set từ user_interactions  │
└────────┬─────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  5. Hybrid Score (A/B weighted)                               │
│                                                              │
│   score = w_sim   × cosine_similarity(user, doc)             │
│         + w_pop   × log(1 + popularity) / 10                 │
│         + w_tag   × min(tag_count / 5, 1.0)                  │
│         + w_rec   × exp(−age_days × ln2 / 30)                │
│                                                              │
│   Group A: w = [0.6, 0.2, 0.1, 0.1]  (popularity-oriented)  │
│   Group B: w = [0.7, 0.1, 0.1, 0.1]  (similarity-oriented)  │
└────────┬─────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  6. ML Re-rank (top 100 candidates)  │
│   feature vector (6 chiều):          │
│   [sim, pop, recency, tag_overlap,   │
│    language_match, role_match]       │
│   → LightGBM predict → sort         │
└────────┬─────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  7. Cache Redis (TTL 300s)            │
│   key: rec:{user_id}                 │
│   invalidate on: any new interaction │
└──────────────────────────────────────┘
```

### A/B Testing

Mỗi user được gán ngẫu nhiên vào group `A` hoặc `B` khi tạo profile lần đầu và **không đổi**. Group ảnh hưởng đến trọng số hybrid score:

| | Group A | Group B |
|---|---|---|
| Cosine similarity | 0.6 | 0.7 |
| Popularity | 0.2 | 0.1 |
| Tag boost | 0.1 | 0.1 |
| Recency | 0.1 | 0.1 |

`ab_group` được trả về trong mọi response để các service analytics downstream thu thập và so sánh CTR giữa hai nhóm.

---

## Kafka Event Contracts

Service lắng nghe **3 Kafka topics**. Các service khác phải publish đúng schema sau.

### Topic: `document-events`

Consumer: `DocumentConsumer` — encode tài liệu thành vector và upsert vào DB.

```json
{
  "event_type": "DOCUMENT_UPSERT",
  "document_id": "uuid-string",
  "title": "Giới thiệu về Machine Learning",
  "description": "Mô tả ngắn...",
  "content": "Nội dung đầy đủ (có thể rỗng)...",
  "tags": ["machine-learning", "python", "ai"],
  "categories": ["cntt", "ai"],
  "language": "vi",
  "faculty": "Khoa Công nghệ thông tin",
  "author_id": "uuid-string",
  "author_role": "TEACHER",
  "author_display_name": "TS. Nguyễn Văn A"
}
```

`event_type` có thể là:
- `DOCUMENT_UPSERT` — thêm mới hoặc cập nhật tài liệu
- `DOCUMENT_DELETE` — xóa tài liệu khỏi recommendation pool

**Trường bắt buộc:** `event_type`, `document_id`  
**Trường nên có:** `title`, `description`, `tags`, `faculty`, `author_role` — càng đầy đủ embedding càng chính xác

---

### Topic: `user-events`

Consumer: `UserConsumer` — encode profile người dùng và upsert vào DB. `ab_group` được giữ nguyên nếu user đã tồn tại.

```json
{
  "event_type": "USER_UPDATE",
  "user_id": "uuid-string",
  "username": "nguyen.van.a",
  "display_name": "Nguyễn Văn A",
  "role": "STUDENT",
  "faculty": "Khoa Công nghệ thông tin",
  "interests": ["machine-learning", "web", "database"]
}
```

`role` hợp lệ: `STUDENT`, `TEACHER`, `ADMIN`

**Khi nào publish:** khi user đăng ký, cập nhật profile, thay đổi khoa/role.

---

### Topic: `recommendation-events`

Consumer: `InteractionConsumer` — cập nhật embedding người dùng theo hành động.

```json
{
  "event_type": "USER_INTERACTION",
  "user_id": "uuid-string",
  "document_id": "uuid-string",
  "interaction_type": "download",
  "query": null
}
```

`interaction_type` hợp lệ: `view` | `read` | `download` | `buy` | `bookmark`

**Khi nào publish:**
- Interaction Service: mỗi khi user view/read/download/buy/bookmark
- Search Service: khi user thực hiện tìm kiếm (`interaction_type` = null, `query` = text)

> **Lưu ý:** Nếu `query` có giá trị và `interaction_type` là null → service xử lý như search log (blend query embedding).

---

## REST API

### Authentication

Trong môi trường production, API Gateway phải inject header `X-User-Id` vào mọi request trước khi forward đến service này. Service không tự xác thực JWT.

```
Client → API Gateway (verify JWT → extract user_id)
                    → forward + header X-User-Id: {user_id}
                    → Recommendation Service
```

Trong `DEV_MODE=true`: `X-User-Id` không bắt buộc, có thể truyền `user_id` qua query param hoặc request body.

---

### `GET /health`

Health check — dùng bởi Eureka, load balancer, và Docker healthcheck.

**Response:**
```json
{
  "status": "UP",
  "service": "recommendation-service",
  "database": "UP",
  "redis": "UP"
}
```

---

### `GET /recommendations`

Lấy danh sách tài liệu gợi ý cho người dùng.

**Request:**
```
GET /recommendations?limit=20
Header: X-User-Id: {user_id}
```

| Param | Type | Default | Mô tả |
|---|---|---|---|
| `limit` | int | 20 | Số kết quả trả về (1–100) |

**Response:**
```json
{
  "user_id": "uuid-string",
  "ab_group": "A",
  "total": 10,
  "recommendations": [
    {
      "document_id": "uuid-string",
      "title": "Khóa luận tốt nghiệp: Xây dựng Chatbot tư vấn tuyển sinh",
      "description": "...",
      "tags": ["web", "machine-learning", "python"],
      "categories": ["ai", "co-so-du-lieu"],
      "language": "vi",
      "faculty": "Khoa Công nghệ thông tin",
      "author_id": "uuid-string",
      "author_role": "TEACHER",
      "popularity_score": 254.4,
      "score": 0.5916,
      "reason": "Based on your activity"
    }
  ],
  "cached": false
}
```

**`reason` values:** `Highly relevant to your interests` | `Based on your activity` | `Popular in your field` | `You might like this` | `Trending`

**Cold start:** Nếu user chưa có embedding (user mới hoàn toàn) → trả về trending documents, `score: 0.0`, `reason: "Trending"`.

---

### `POST /interactions`

Ghi nhận tương tác và cập nhật embedding người dùng ngay lập tức.

> **Lưu ý:** Trong kiến trúc production, Interaction Service nên publish event lên Kafka topic `recommendation-events` thay vì gọi trực tiếp endpoint này. Endpoint này vẫn hoạt động cho các trường hợp cần đồng bộ ngay.

**Request:**
```
POST /interactions
Header: X-User-Id: {user_id}
Content-Type: application/json

{
  "document_id": "uuid-string",
  "interaction_type": "download"
}
```

**Response:**
```json
{
  "id": "uuid-string",
  "user_id": "uuid-string",
  "document_id": "uuid-string",
  "interaction_type": "download"
}
```

**Side effects:**
- Insert vào `user_interactions`
- Update `popularity_score` của document
- Blend user embedding (EMA với weight theo loại tương tác)
- Invalidate Redis cache của user

---

### `POST /search-log`

Ghi nhận query tìm kiếm và cập nhật embedding người dùng.

> **Tương tự:** Search Service nên publish lên Kafka. Endpoint này cho phép gọi trực tiếp.

**Request:**
```
POST /search-log
Header: X-User-Id: {user_id}
Content-Type: application/json

{
  "query": "machine learning python"
}
```

**Response:**
```json
{
  "id": "uuid-string",
  "user_id": "uuid-string",
  "query": "machine learning python"
}
```

**Side effects:**
- Insert vào `search_history`
- Encode query → blend into user embedding (weight 0.1)
- Tìm docs matching keywords → blend avg embedding (weight 0.15)
- Invalidate Redis cache

---

## Cấu trúc thư mục

```
docube_recommendation_service/
│
├── app/
│   ├── main.py                        # FastAPI entry point, lifespan startup/shutdown
│   │
│   ├── api/
│   │   ├── recommendation.py          # GET /health, GET /recommendations
│   │   ├── interaction.py             # POST /interactions
│   │   ├── search_log.py              # POST /search-log
│   │   ├── documents.py               # DEV only: xem danh sách tài liệu
│   │   ├── auth.py                    # DEV only: login mock
│   │   └── validation.py              # DEV only: validate event schemas
│   │
│   ├── consumers/
│   │   ├── consumer_manager.py        # Khởi/dừng toàn bộ Kafka consumers
│   │   ├── document_consumer.py       # document-events → encode → upsert
│   │   ├── user_consumer.py           # user-events → encode → upsert
│   │   └── interaction_consumer.py    # recommendation-events → process
│   │
│   ├── core/
│   │   ├── config.py                  # Settings từ env (pydantic-settings)
│   │   ├── eureka_client.py           # Đăng ký / huỷ Eureka
│   │   ├── middleware.py              # UserPermissionMiddleware (X-User-Id header)
│   │   └── security.py               # UserContext, get_current_user dependency
│   │
│   ├── ml/
│   │   ├── embedding.py               # encode_document, encode_user, encode_query, blend
│   │   ├── reranker.py                # Load LightGBM, build_feature_vector, rerank()
│   │   └── ab_testing.py             # A/B weight configs
│   │
│   ├── models/
│   │   ├── events.py                  # Pydantic: DocumentEvent, UserEvent, InteractionEvent
│   │   └── schemas.py                 # Pydantic: RecommendationItem, InteractionRequest, …
│   │
│   ├── repositories/
│   │   ├── database.py                # asyncpg pool: init_db_pool, get_pool
│   │   ├── document_repo.py           # upsert, ann_search, get_trending, find_by_keywords
│   │   ├── user_repo.py               # upsert_user, get_user, update_embedding, get_ab_group
│   │   ├── interaction_repo.py        # insert_interaction, get_recent_document_ids
│   │   └── search_history_repo.py     # insert_search, get_recent_searches
│   │
│   └── services/
│       ├── recommendation_service.py  # Pipeline chính: cache→ANN→score→rerank
│       ├── interaction_service.py     # Xử lý tương tác, blend embedding, Kafka publish
│       ├── search_service.py          # Xử lý search log, keyword blending
│       └── cache_service.py           # Redis get/set/invalidate/health
│
├── tests/
│   ├── seed/seed_data.py              # Seed 200 docs, 30 users, 600 interactions (tiếng Việt)
│   └── ui/                            # Playwright E2E tests
│
├── frontend/                          # Next.js demo UI
├── schema.sql                         # DDL: tables, pgvector extension, IVFFLAT index
├── docker-compose.test.yml            # Stack đầy đủ cho dev/test
├── Dockerfile                         # Image production cho service này
├── Dockerfile.seed                    # Image cho seed runner
└── requirements.txt
```

---

## Môi trường & Cấu hình

### File `.env` (production)

Tạo file `.env` tại thư mục gốc với nội dung sau:

```env
# ── Application ───────────────────────────────────
DEV_MODE=false
SERVICE_NAME=recommendation-service
SERVICE_PORT=8000
SERVICE_HOST=<IP hoặc hostname của máy chủ này>

# ── PostgreSQL ────────────────────────────────────
POSTGRES_HOST=<host>
POSTGRES_PORT=5432
POSTGRES_DB=horob1_docub_rm_service
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<password>

# ── Redis ─────────────────────────────────────────
REDIS_HOST=<host>
REDIS_PORT=6379
REDIS_PASSWORD=<password>
REDIS_DB=5
REDIS_CACHE_TTL=300

# ── Kafka ─────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=<broker1:port,broker2:port>
KAFKA_SECURITY_PROTOCOL=SASL_PLAINTEXT
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=<username>
KAFKA_SASL_PASSWORD=<password>
KAFKA_GROUP_ID=rm-service-group

# ── Eureka ────────────────────────────────────────
EUREKA_SERVER=http://<eureka-host>:9000/eureka

# ── ML ────────────────────────────────────────────
RERANKER_MODEL_PATH=models/reranker.pkl
ANN_CANDIDATES=200

# ── CORS (chỉ cần nếu DEV_MODE=true) ─────────────
FRONTEND_URL=http://localhost:3000
```

### Bảng biến môi trường đầy đủ

| Biến | Bắt buộc | Mặc định | Mô tả |
|---|---|---|---|
| `DEV_MODE` | | `false` | Bật dev endpoints, tắt auth bắt buộc, mở CORS |
| `SERVICE_NAME` | | `recommendation-service` | Tên đăng ký Eureka |
| `SERVICE_PORT` | | `8000` | Port service lắng nghe |
| `SERVICE_HOST` | ✓ prod | `localhost` | Host đăng ký Eureka (IP thực của container/máy chủ) |
| `POSTGRES_HOST` | ✓ | `localhost` | |
| `POSTGRES_PORT` | | `5432` | |
| `POSTGRES_DB` | | `horob1_docub_rm_service` | |
| `POSTGRES_USER` | | `postgres` | |
| `POSTGRES_PASSWORD` | ✓ | `2410` | |
| `REDIS_HOST` | ✓ | `localhost` | |
| `REDIS_PORT` | | `6379` | |
| `REDIS_PASSWORD` | ✓ | `2410` | |
| `REDIS_DB` | | `5` | Database index Redis |
| `REDIS_CACHE_TTL` | | `300` | TTL cache gợi ý (giây) |
| `KAFKA_BOOTSTRAP_SERVERS` | ✓ | `localhost:7092` | |
| `KAFKA_SECURITY_PROTOCOL` | | `SASL_PLAINTEXT` | `PLAINTEXT` cho môi trường nội bộ không cần auth |
| `KAFKA_SASL_MECHANISM` | | `PLAIN` | Bỏ qua nếu `PLAINTEXT` |
| `KAFKA_SASL_USERNAME` | | `horob1` | Bỏ qua nếu `PLAINTEXT` |
| `KAFKA_SASL_PASSWORD` | | `2410` | Bỏ qua nếu `PLAINTEXT` |
| `KAFKA_GROUP_ID` | | `rm-service-group` | Consumer group — mỗi instance dùng chung group để cân bằng tải |
| `EUREKA_SERVER` | | `http://localhost:9000/eureka` | |
| `RERANKER_MODEL_PATH` | | `models/reranker.pkl` | Nếu file không tồn tại → fallback LogisticRegression |
| `ANN_CANDIDATES` | | `200` | Số candidates lấy từ pgvector trước khi rerank |
| `FRONTEND_URL` | dev | — | CORS allowed origin |

---

## Kết nối với các service khác

### Checklist cho team tích hợp

**Document Service cần làm:**
- [ ] Publish lên topic `document-events` mỗi khi tài liệu được tạo/cập nhật/xóa
- [ ] `document_id` phải là UUID stable (không đổi khi update)
- [ ] Không cần gọi API của service này

**User Service cần làm:**
- [ ] Publish lên topic `user-events` khi user đăng ký hoặc cập nhật profile
- [ ] `user_id` phải khớp với `user_id` trong các service khác (dùng chung UUID)
- [ ] Không cần gọi API của service này

**Interaction / Payment Service cần làm:**
- [ ] Publish lên topic `recommendation-events` sau mỗi tương tác
- [ ] `interaction_type` phải là một trong: `view`, `read`, `download`, `buy`, `bookmark`

**Search Service cần làm:**
- [ ] Publish lên topic `recommendation-events` sau mỗi search của user
- [ ] Để `interaction_type: null`, đặt `query: "từ khóa tìm kiếm"`

**API Gateway cần làm:**
- [ ] Inject header `X-User-Id: {user_id}` vào mọi request đến `/recommendations`, `/interactions`, `/search-log`
- [ ] Route `GET /recommendations` → service này (qua Eureka load balancer)
- [ ] Service name đăng ký Eureka: `recommendation-service`

**Frontend / Client cần làm:**
- [ ] Gọi `GET /recommendations?limit=20` (qua Gateway) để hiển thị danh sách gợi ý
- [ ] Dùng `ab_group` trong response để tracking A/B analytics
- [ ] Dùng `reason` để hiển thị label cho user ("Vì bạn đã xem...", "Phổ biến trong khoa bạn", v.v.)

