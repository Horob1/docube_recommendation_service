# Hướng dẫn Deploy với Docker

Tài liệu này mô tả cách đóng gói và triển khai `recommendation-service` trong môi trường production sử dụng Docker.

---

## Mục lục

1. [Yêu cầu](#yêu-cầu)
2. [Chuẩn bị .env](#chuẩn-bị-env)
3. [Build image](#build-image)
4. [Chạy với docker run](#chạy-với-docker-run)
5. [Chạy với docker-compose](#chạy-với-docker-compose)
6. [Chạy môi trường dev/test đầy đủ](#chạy-môi-trường-devtest-đầy-đủ)
7. [Schema database](#schema-database)
8. [Kiểm tra sau deploy](#kiểm-tra-sau-deploy)
9. [Quản lý lifecycle](#quản-lý-lifecycle)
10. [Troubleshooting](#troubleshooting)

---

## Yêu cầu

| Thành phần | Phiên bản tối thiểu | Ghi chú |
|---|---|---|
| Docker | 24+ | Docker Desktop hoặc Docker Engine |
| Docker Compose | v2 | `docker compose` (không dấu gạch ngang) |
| RAM cho Docker | 4 GB | Kafka + Postgres + Service |
| Disk | 5 GB | Image + volumes |

**Các service phải có sẵn trước khi chạy:**
- PostgreSQL 16 với extension `pgvector`
- Redis 7
- Apache Kafka (bất kỳ broker nào tương thích)
- Spring Cloud Eureka (tùy chọn — bỏ qua nếu `DEV_MODE=true`)

---

## Chuẩn bị .env

Tạo file `.env` tại thư mục gốc project (cùng cấp với `Dockerfile`):

```bash
cp .env.example .env   # nếu có file mẫu
# hoặc tạo thủ công
```

Nội dung `.env` tối thiểu để chạy:

```env
DEV_MODE=false
SERVICE_HOST=<IP máy chủ này, ví dụ: 192.168.1.10>

POSTGRES_HOST=<postgres-host>
POSTGRES_PORT=5432
POSTGRES_DB=horob1_docub_rm_service
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<mật khẩu>

REDIS_HOST=<redis-host>
REDIS_PORT=6379
REDIS_PASSWORD=<mật khẩu>
REDIS_DB=5

KAFKA_BOOTSTRAP_SERVERS=<broker:port>
KAFKA_SECURITY_PROTOCOL=SASL_PLAINTEXT
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=<username>
KAFKA_SASL_PASSWORD=<mật khẩu>
KAFKA_GROUP_ID=rm-service-group

EUREKA_SERVER=http://<eureka-host>:9000/eureka
```

> **Lưu ý:** File `.env` không được commit lên git (đã có trong `.gitignore`). Trong production nên dùng Docker Secrets hoặc Vault.

---

## Build image

```bash
# Build image với tag version
docker build -t docube/recommendation-service:1.0.0 .

# Hoặc tag latest
docker build -t docube/recommendation-service:latest .
```

**Lần đầu build sẽ download:**
- Python packages (~500MB tổng, trong đó torch CPU ~200MB)
- Model `all-MiniLM-L6-v2` (~90MB) — download lần đầu khi service khởi động, không phải lúc build

**Lần build sau** (chỉ đổi code): ~10 giây nhờ Docker layer cache.

```bash
# Xem kích thước image
docker images docube/recommendation-service
```

---

## Chạy với docker run

Cách đơn giản nhất để chạy một container đơn lẻ, kết nối vào hạ tầng đã có sẵn:

```bash
docker run -d \
  --name rm-service \
  --env-file .env \
  -p 8000:8000 \
  --restart unless-stopped \
  docube/recommendation-service:latest
```

**Xem logs:**
```bash
docker logs -f rm-service
```

**Dừng:**
```bash
docker stop rm-service
docker rm rm-service
```

---

## Chạy với docker-compose

Nếu muốn quản lý service cùng với các dependency (Redis, Postgres, v.v.) bằng một file compose:

Tạo file `docker-compose.prod.yml`:

```yaml
services:
  recommendation-service:
    image: docube/recommendation-service:latest
    # hoặc build tại chỗ:
    # build: .
    container_name: rm-service
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./models:/app/models   # mount thư mục chứa reranker.pkl nếu có
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      start_period: 60s
      retries: 3
    networks:
      - docube-network

networks:
  docube-network:
    external: true   # network chung của toàn bộ hệ thống Docube
```

```bash
# Khởi động
docker compose -f docker-compose.prod.yml up -d

# Xem logs
docker compose -f docker-compose.prod.yml logs -f

# Dừng
docker compose -f docker-compose.prod.yml down
```

---

## Chạy môi trường dev/test đầy đủ

File `docker-compose.test.yml` bao gồm toàn bộ stack (Postgres, Redis, Kafka, Zookeeper, Service, Frontend, Seed):

```bash
# Khởi động lần đầu (build + seed dữ liệu)
docker compose -f docker-compose.test.yml up --build

# Lần sau (đã có cache)
docker compose -f docker-compose.test.yml up

# Chạy ngầm
docker compose -f docker-compose.test.yml up -d --build
```

**Thứ tự khởi động tự động:**
```
postgres ──healthy──► seed (chạy 1 lần, sau đó exit 0)
redis ──healthy──────┐
kafka ──healthy──────┴──► recommendation-service ──healthy──► frontend
```

**Xem trạng thái tất cả container:**
```bash
docker compose -f docker-compose.test.yml ps
```

**Chỉ rebuild một service:**
```bash
docker compose -f docker-compose.test.yml up --build recommendation-service
```

---

## Schema database

Database phải được khởi tạo trước khi service chạy:

```bash
# Chạy migration (idempotent — an toàn khi chạy lại nhiều lần)
docker exec -i rm-postgres psql -U postgres -d horob1_docub_rm_service \
  < schema.sql
```

Hoặc nếu chạy psql từ máy local:
```bash
psql -h <postgres-host> -U postgres -d horob1_docub_rm_service -f schema.sql
```

**Kiểm tra pgvector đã được cài:**
```bash
docker exec -it rm-postgres psql -U postgres -d horob1_docub_rm_service \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

Expected output:
```
 extname | extversion
---------+------------
 vector  | 0.7.0
```

---

## Kiểm tra sau deploy

### 1. Health check
```bash
curl http://localhost:8000/health
```
Expected:
```json
{"status": "UP", "service": "recommendation-service", "database": "UP", "redis": "UP"}
```

### 2. Swagger UI (DEV_MODE=true)
```
http://localhost:8000/docs
```

### 3. Kiểm tra service đã đăng ký Eureka
```
http://<eureka-host>:9000/  → tìm "RECOMMENDATION-SERVICE" trong danh sách
```

### 4. Kiểm tra Kafka consumers hoạt động
```bash
docker logs rm-service | grep "consumer"
```
Expected (3 dòng):
```
INFO │ consumers │ ✅ Document consumer started
INFO │ consumers │ ✅ User consumer started
INFO │ consumers │ ✅ Interaction consumer started
```

### 5. Test API nhanh (cần có user_id trong DB)
```bash
# Với X-User-Id header (production mode)
curl "http://localhost:8000/recommendations?limit=5" \
  -H "X-User-Id: <user_id>"

# Hoặc DEV_MODE=true
curl "http://localhost:8000/recommendations?user_id=<user_id>&limit=5"
```

---

## Quản lý lifecycle

### Xem logs
```bash
# Follow logs realtime
docker logs -f rm-service

# Lọc log level
docker logs rm-service 2>&1 | grep "ERROR"

# N dòng cuối
docker logs --tail 100 rm-service
```

### Restart service (reload code mới)
```bash
# Sau khi thay đổi code — phải rebuild
docker compose -f docker-compose.test.yml up --build recommendation-service

# Chỉ restart container (không reload code)
docker compose -f docker-compose.test.yml restart recommendation-service
```

### Scale (chạy nhiều instance)
```bash
# Chạy 3 instance (tất cả cùng KAFKA_GROUP_ID → Kafka tự cân bằng tải)
docker compose -f docker-compose.prod.yml up -d --scale recommendation-service=3
```

> Lưu ý: khi scale, cần Redis chung để cache đồng bộ giữa các instance.

### Dừng và xóa

```bash
# Dừng, giữ nguyên volumes (data)
docker compose -f docker-compose.test.yml down

# Dừng + xóa toàn bộ volumes (reset sạch DB, Redis)
docker compose -f docker-compose.test.yml down -v

# Xóa tất cả image đã build
docker compose -f docker-compose.test.yml down --rmi all
```

### Cập nhật lên version mới
```bash
# 1. Build image mới
docker build -t docube/recommendation-service:1.1.0 .

# 2. Update tag trong docker-compose.prod.yml
# image: docube/recommendation-service:1.1.0

# 3. Restart với zero-downtime (nếu scale >= 2)
docker compose -f docker-compose.prod.yml up -d --no-deps recommendation-service
```

---

## Troubleshooting

### Service không kết nối được PostgreSQL
```bash
# Kiểm tra kết nối từ trong container
docker exec -it rm-service python -c "
import asyncio, asyncpg
async def test():
    conn = await asyncpg.connect('postgresql://postgres:PASSWORD@HOST:5432/DB')
    print(await conn.fetchval('SELECT version()'))
asyncio.run(test())
"
```

### Service không kết nối được Kafka
```bash
# Kiểm tra log consumer
docker logs rm-service 2>&1 | grep -i "kafka\|consumer\|broker"
```

Lỗi thường gặp:
- `SASL authentication failed` → kiểm tra `KAFKA_SASL_USERNAME/PASSWORD`
- `[Errno 111] Connection refused` → kiểm tra `KAFKA_BOOTSTRAP_SERVERS` và firewall
- `UNKNOWN_TOPIC_OR_PARTITION` → topic chưa được tạo, yêu cầu Kafka admin tạo topic

### Redis cache không hoạt động
```bash
# Test redis từ trong container
docker exec -it rm-service python -c "
import redis
r = redis.Redis(host='REDIS_HOST', port=6379, password='PASSWORD', db=5)
print(r.ping())
"
```

### Model embedding download chậm / lỗi
Model `all-MiniLM-L6-v2` được download từ HuggingFace khi service khởi động lần đầu. Nếu không có internet:

```bash
# Pre-download model vào volume trước
docker run --rm \
  -v ./hf_cache:/root/.cache/huggingface \
  python:3.12-slim \
  pip install sentence-transformers && \
  python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Mount cache vào container service
docker run -d \
  --name rm-service \
  --env-file .env \
  -v ./hf_cache:/root/.cache/huggingface \
  -p 8000:8000 \
  docube/recommendation-service:latest
```

### Eureka registration thất bại
Service vẫn chạy bình thường nếu Eureka không khả dụng — chỉ log warning. Để bỏ qua hoàn toàn:
```env
DEV_MODE=true
```

### Port 8000 đã bị chiếm
```bash
# Đổi port mapping
docker run -p 8001:8000 ...
# Hoặc trong docker-compose:
# ports: ["8001:8000"]
```
