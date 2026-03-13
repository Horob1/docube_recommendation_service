"""
Auto Seed Script — populates the database with Vietnamese university mock data.

Uses sentence-transformers to generate REAL embeddings.
Seeds: 200 documents, 30 users, 600+ interactions.

Domain: Docube — tài liệu học thuật đại học Việt Nam
  - Tài liệu: bài giảng, khóa luận, đề thi, bài tập, tài liệu tham khảo
  - Người dùng: sinh viên, giảng viên từ nhiều khoa
  - Tương tác: view, read, download, buy, bookmark

Usage:
    python -m tests.seed.seed_data
    # or in Docker:
    docker compose -f docker-compose.test.yml run seed
"""

import asyncio
import logging
import os
import random
import sys
import time
import uuid

import asyncpg
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("seed")

# ── Config ────────────────────────────────────────────────────────────
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "horob1_docub_rm_service")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "2410")

NUM_DOCUMENTS = 200
NUM_USERS = 30
NUM_INTERACTIONS = 600
EMBEDDING_DIM = 384

# ── Academic structure ────────────────────────────────────────────────

FACULTIES = {
    "Khoa Công nghệ thông tin": {
        "departments": [
            "Bộ môn Khoa học máy tính",
            "Bộ môn Hệ thống thông tin",
            "Bộ môn Kỹ thuật phần mềm",
            "Bộ môn Mạng và truyền thông",
            "Bộ môn Trí tuệ nhân tạo",
        ],
        "majors": [
            "Khoa học máy tính",
            "Hệ thống thông tin",
            "Kỹ thuật phần mềm",
            "An toàn thông tin",
            "Trí tuệ nhân tạo",
        ],
        "subject_codes": ["IT3190", "IT4062", "IT4063", "IT4080", "IT3100", "IT4090", "IT3150"],
        "categories": ["cntt", "lap-trinh", "ai", "co-so-du-lieu", "mang-may-tinh"],
        "tags_pool": ["python", "java", "sql", "machine-learning", "ai", "deep-learning",
                      "web", "api", "docker", "kubernetes", "linux", "network", "security",
                      "database", "postgresql", "redis", "microservices", "nlp", "pytorch"],
        "topics": [
            ("Giới thiệu về Machine Learning và ứng dụng", "lecture"),
            ("Lập trình hướng đối tượng với Java", "lecture"),
            ("Cơ sở dữ liệu nâng cao - PostgreSQL", "lecture"),
            ("Thiết kế và phân tích giải thuật", "lecture"),
            ("Mạng máy tính - giao thức TCP/IP", "lecture"),
            ("Bảo mật thông tin cơ bản", "lecture"),
            ("Trí tuệ nhân tạo - tìm kiếm và suy luận", "lecture"),
            ("Kỹ thuật phần mềm - quy trình Agile Scrum", "lecture"),
            ("Deep Learning với PyTorch", "lecture"),
            ("Xây dựng RESTful API với FastAPI", "lecture"),
            ("Kiến trúc microservices", "lecture"),
            ("Containerization với Docker và Kubernetes", "lecture"),
            ("Xử lý ngôn ngữ tự nhiên tiếng Việt", "lecture"),
            ("Hệ quản trị cơ sở dữ liệu MongoDB", "lecture"),
            ("Lập trình Web - HTML, CSS, JavaScript", "lecture"),
            ("Khóa luận tốt nghiệp: Hệ thống gợi ý tài liệu học tập", "thesis"),
            ("Khóa luận tốt nghiệp: Ứng dụng AI trong phát hiện gian lận", "thesis"),
            ("Khóa luận tốt nghiệp: Xây dựng Chatbot tư vấn tuyển sinh", "thesis"),
            ("Đề thi cuối kỳ - Cơ sở dữ liệu 2023", "exam"),
            ("Đề thi giữa kỳ - Lập trình Java 2024", "exam"),
            ("Bài tập lớn - Xây dựng ứng dụng Todo List", "exercise"),
            ("Bài tập thực hành - SQL nâng cao", "exercise"),
            ("Tài liệu tham khảo: Clean Code - Robert C. Martin", "reference"),
            ("Tài liệu tham khảo: System Design Interview", "reference"),
        ],
    },
    "Khoa Kinh tế": {
        "departments": [
            "Bộ môn Kinh tế học",
            "Bộ môn Quản trị kinh doanh",
            "Bộ môn Tài chính - Ngân hàng",
            "Bộ môn Marketing",
            "Bộ môn Kế toán - Kiểm toán",
        ],
        "majors": [
            "Kinh tế học",
            "Quản trị kinh doanh",
            "Tài chính - Ngân hàng",
            "Marketing",
            "Kế toán",
        ],
        "subject_codes": ["EC2001", "EC3010", "FIN2050", "MKT3001", "ACC2010"],
        "categories": ["kinh-te", "quan-tri", "tai-chinh", "marketing", "ke-toan"],
        "tags_pool": ["kinh-te-vi-mo", "kinh-te-vi-mo", "tai-chinh", "ngan-hang",
                      "marketing", "thuong-mai-dien-tu", "ke-toan", "quan-tri-rui-ro",
                      "chung-khoan", "dau-tu", "phan-tich-tai-chinh", "erp"],
        "topics": [
            ("Kinh tế vĩ mô - các chính sách kinh tế Việt Nam", "lecture"),
            ("Quản trị kinh doanh căn bản", "lecture"),
            ("Tài chính doanh nghiệp", "lecture"),
            ("Marketing số trong thời đại 4.0", "lecture"),
            ("Kế toán tài chính - chuẩn mực Việt Nam", "lecture"),
            ("Phân tích tài chính và đầu tư", "lecture"),
            ("Thương mại điện tử và kinh doanh trực tuyến", "lecture"),
            ("Quản trị rủi ro tài chính", "lecture"),
            ("Khóa luận: Tác động của fintech đến ngân hàng truyền thống", "thesis"),
            ("Khóa luận: Chiến lược marketing cho startup", "thesis"),
            ("Đề thi cuối kỳ - Kinh tế vi mô 2024", "exam"),
            ("Bài tập phân tích báo cáo tài chính", "exercise"),
            ("Tài liệu tham khảo: Nguyên lý kế toán Việt Nam", "reference"),
        ],
    },
    "Khoa Điện - Điện tử": {
        "departments": [
            "Bộ môn Điện tử cơ bản",
            "Bộ môn Điều khiển tự động",
            "Bộ môn Viễn thông",
            "Bộ môn Kỹ thuật điện",
        ],
        "majors": [
            "Kỹ thuật điện tử",
            "Kỹ thuật điều khiển",
            "Kỹ thuật viễn thông",
            "Kỹ thuật điện",
        ],
        "subject_codes": ["EE2010", "EE3020", "TL3001", "CT2050"],
        "categories": ["dien-tu", "dieu-khien", "vien-thong", "ky-thuat-dien"],
        "tags_pool": ["arduino", "raspberry-pi", "vi-dieu-khien", "plc", "dieu-khien-pid",
                      "iot", "rf", "mach-dien", "bien-tan", "cam-bien", "robot"],
        "topics": [
            ("Điện tử tương tự - khuếch đại thuật toán", "lecture"),
            ("Lập trình vi điều khiển Arduino", "lecture"),
            ("IoT - kết nối thiết bị thông minh", "lecture"),
            ("Điều khiển PID và ứng dụng", "lecture"),
            ("Kỹ thuật viễn thông cơ bản", "lecture"),
            ("Robot công nghiệp - lập trình và điều khiển", "lecture"),
            ("Khóa luận: Hệ thống nhà thông minh IoT", "thesis"),
            ("Đề thi - Điện tử số 2023", "exam"),
            ("Bài tập mô phỏng mạch điện với Proteus", "exercise"),
            ("Tài liệu tham khảo: Microcontrollers and the C Language", "reference"),
        ],
    },
    "Khoa Toán - Cơ - Tin học": {
        "departments": [
            "Bộ môn Toán học",
            "Bộ môn Xác suất thống kê",
            "Bộ môn Toán ứng dụng",
        ],
        "majors": [
            "Toán học",
            "Thống kê",
            "Toán tin",
        ],
        "subject_codes": ["MA1101", "MA2010", "ST3001", "MA3050"],
        "categories": ["toan-hoc", "xac-suat", "thong-ke", "toan-ung-dung"],
        "tags_pool": ["dai-so-tuyen-tinh", "giai-tich", "xac-suat", "thong-ke",
                      "toi-uu-hoa", "matlab", "r-language", "mo-hinh-hoa"],
        "topics": [
            ("Đại số tuyến tính ứng dụng trong Machine Learning", "lecture"),
            ("Giải tích - chuỗi số và tích phân", "lecture"),
            ("Xác suất thống kê cho kỹ sư", "lecture"),
            ("Tối ưu hóa - gradient descent và ứng dụng", "lecture"),
            ("Phân tích dữ liệu với R", "lecture"),
            ("Khóa luận: Ứng dụng thống kê Bayes trong dự báo", "thesis"),
            ("Đề thi - Xác suất thống kê 2024", "exam"),
            ("Bài tập giải tích nhiều biến", "exercise"),
        ],
    },
}

DOCUMENT_TYPES = ["thesis", "lecture", "exam", "exercise", "reference"]
ROLES = ["STUDENT", "TEACHER"]
LANGUAGES = ["vi", "vi", "vi", "en"]   # weighted towards Vietnamese
ACADEMIC_YEARS = ["2022-2023", "2023-2024", "2024-2025"]
# Interaction weighted: read and buy are less frequent but high signal
INTERACTION_TYPES = ["view", "view", "view", "read", "read", "download", "bookmark", "buy"]


def _generate_description(title: str, faculty: str, doc_type: str) -> str:
    type_map = {
        "thesis": "Khóa luận tốt nghiệp nghiên cứu về",
        "lecture": "Bài giảng tổng quan về",
        "exam": "Đề thi kiểm tra kiến thức về",
        "exercise": "Bài tập thực hành giúp rèn luyện kỹ năng về",
        "reference": "Tài liệu tham khảo chuyên sâu về",
    }
    prefix = type_map.get(doc_type, "Tài liệu về")
    return (
        f"{prefix} {title.lower()}. "
        f"Thuộc chương trình đào tạo của {faculty}. "
        f"Phù hợp cho sinh viên và giảng viên muốn nắm vững kiến thức nền tảng và nâng cao."
    )


def _generate_content(title: str, faculty: str, doc_type: str) -> str:
    return (
        f"Tài liệu \"{title}\" thuộc {faculty}. "
        f"Đây là {doc_type} bao gồm lý thuyết cơ bản, các ví dụ thực tế và bài tập ứng dụng. "
        f"Nội dung được biên soạn theo chuẩn chương trình khung của Bộ Giáo dục và Đào tạo. "
        f"Tài liệu phù hợp cho sinh viên từ năm 1 đến năm 4, cũng như giảng viên trong quá trình "
        f"giảng dạy và nghiên cứu. Nội dung bao gồm: phần lý thuyết, ví dụ minh họa, "
        f"bài tập có lời giải, và câu hỏi ôn tập cuối chương."
    )


async def wait_for_postgres():
    """Wait for PostgreSQL to be ready."""
    logger.info("⏳ Waiting for PostgreSQL at %s:%d ...", POSTGRES_HOST, POSTGRES_PORT)
    for attempt in range(30):
        try:
            conn = await asyncpg.connect(
                host=POSTGRES_HOST, port=POSTGRES_PORT,
                user=POSTGRES_USER, password=POSTGRES_PASSWORD,
                database="postgres",
            )
            await conn.close()
            logger.info("✅ PostgreSQL is ready")
            return
        except Exception:
            await asyncio.sleep(2)
    raise RuntimeError("PostgreSQL not available after 60 seconds")


async def ensure_database():
    """Create the database if it doesn't exist."""
    conn = await asyncpg.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", POSTGRES_DB
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{POSTGRES_DB}"')
            logger.info("📦 Created database: %s", POSTGRES_DB)
        else:
            logger.info("📦 Database already exists: %s", POSTGRES_DB)
    finally:
        await conn.close()


async def create_schema(pool: asyncpg.Pool):
    """Create pgvector extension, tables, and IVFFLAT index."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "schema.sql")
    if not os.path.exists(schema_path):
        schema_path = "schema.sql"

    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()

    async with pool.acquire() as conn:
        await conn.execute(sql)
    logger.info("✅ Schema created (tables + pgvector + IVFFLAT)")


async def seed_documents(pool: asyncpg.Pool, model):
    """Seed 200 documents with real sentence-transformer embeddings."""
    logger.info("📄 Seeding %d documents ...", NUM_DOCUMENTS)

    # Build flat list of all document templates across faculties
    all_templates = []
    for faculty_name, faculty_data in FACULTIES.items():
        for title, doc_type in faculty_data["topics"]:
            tags = random.sample(faculty_data["tags_pool"], min(4, len(faculty_data["tags_pool"])))
            categories = random.sample(faculty_data["categories"], min(2, len(faculty_data["categories"])))
            all_templates.append({
                "faculty": faculty_name,
                "tags": tags,
                "categories": categories,
                "title": title,
                "doc_type": doc_type,
            })

    docs = []
    for i in range(NUM_DOCUMENTS):
        tmpl = all_templates[i % len(all_templates)]

        title = tmpl["title"]
        if i >= len(all_templates):
            title = f"{title} - Phần {i // len(all_templates) + 1}"

        faculty = tmpl["faculty"]
        doc_type = tmpl["doc_type"]

        doc_id = f"doc-{i + 1:04d}"
        tags = tmpl["tags"][:]
        categories = tmpl["categories"][:]
        language = random.choice(LANGUAGES)
        author_id = f"user-{random.randint(1, 10):03d}"
        author_role = "TEACHER" if doc_type in ("lecture", "exam") else random.choice(ROLES)
        description = _generate_description(title, faculty, doc_type)
        content = _generate_content(title, faculty, doc_type)
        popularity = round(random.uniform(0, 300), 1)

        combined = (
            f"Title: {title}\n"
            f"Description: {description}\n"
            f"Tags: {' '.join(tags)}\n"
            f"Categories: {' '.join(categories)}\n"
            f"Faculty: {faculty}\n"
            f"Content: {content[:500]}"
        )

        docs.append({
            "document_id": doc_id,
            "title": title,
            "description": description,
            "content": content,
            "tags": tags,
            "categories": categories,
            "language": language,
            "faculty": faculty,
            "author_id": author_id,
            "author_role": author_role,
            "popularity_score": popularity,
            "combined_text": combined,
        })

    # Batch encode all documents
    texts = [d["combined_text"] for d in docs]
    logger.info("  ⏳ Encoding %d documents with sentence-transformers ...", len(texts))
    t0 = time.time()
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
    logger.info("  ✅ Encoding done in %.1f seconds", time.time() - t0)

    # Batch insert
    async with pool.acquire() as conn:
        for i, doc in enumerate(docs):
            emb_str = _vector_to_str(embeddings[i])
            await conn.execute(
                """
                INSERT INTO documents (
                    document_id, title, description, content,
                    tags, categories, language, faculty,
                    author_id, author_role, embedding,
                    popularity_score, updated_at
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,
                    $9,$10,$11::vector(384),
                    $12, NOW() - ($13 || ' days')::interval
                )
                ON CONFLICT (document_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    content = EXCLUDED.content,
                    tags = EXCLUDED.tags,
                    categories = EXCLUDED.categories,
                    language = EXCLUDED.language,
                    faculty = EXCLUDED.faculty,
                    author_id = EXCLUDED.author_id,
                    author_role = EXCLUDED.author_role,
                    embedding = EXCLUDED.embedding,
                    popularity_score = EXCLUDED.popularity_score,
                    updated_at = EXCLUDED.updated_at
                """,
                doc["document_id"], doc["title"], doc["description"],
                doc["content"], doc["tags"], doc["categories"],
                doc["language"], doc["faculty"],
                doc["author_id"], doc["author_role"],
                emb_str, doc["popularity_score"],
                str(random.randint(1, 90)),
            )

    logger.info("✅ Seeded %d documents", NUM_DOCUMENTS)


async def seed_users(pool: asyncpg.Pool, model):
    """Seed 30 users (sinh viên & giảng viên) with embeddings and random A/B groups."""
    logger.info("👤 Seeding %d users ...", NUM_USERS)

    # User profiles covering different faculties and roles
    user_profiles = [
        # Sinh viên CNTT
        {"username": "nguyenvana",    "display_name": "Nguyễn Văn A",    "role": "STUDENT", "faculty": "Khoa Công nghệ thông tin", "major": "Hệ thống thông tin",   "year": 3, "interests": ["machine-learning", "python", "web", "database"]},
        {"username": "tranthib",      "display_name": "Trần Thị B",      "role": "STUDENT", "faculty": "Khoa Công nghệ thông tin", "major": "Kỹ thuật phần mềm",    "year": 2, "interests": ["java", "web", "api", "microservices"]},
        {"username": "levancuong",    "display_name": "Lê Văn Cường",    "role": "STUDENT", "faculty": "Khoa Công nghệ thông tin", "major": "Khoa học máy tính",    "year": 4, "interests": ["ai", "deep-learning", "research", "nlp"]},
        {"username": "phamthidung",   "display_name": "Phạm Thị Dung",   "role": "STUDENT", "faculty": "Khoa Công nghệ thông tin", "major": "An toàn thông tin",    "year": 3, "interests": ["security", "network", "python", "linux"]},
        {"username": "hoangvane",     "display_name": "Hoàng Văn E",     "role": "STUDENT", "faculty": "Khoa Công nghệ thông tin", "major": "Trí tuệ nhân tạo",     "year": 3, "interests": ["pytorch", "deep-learning", "nlp", "python"]},
        {"username": "dothif",        "display_name": "Đỗ Thị F",        "role": "STUDENT", "faculty": "Khoa Công nghệ thông tin", "major": "Hệ thống thông tin",   "year": 1, "interests": ["database", "sql", "web"]},
        {"username": "buitrung",      "display_name": "Bùi Trung G",     "role": "STUDENT", "faculty": "Khoa Công nghệ thông tin", "major": "Kỹ thuật phần mềm",    "year": 2, "interests": ["java", "microservices", "docker"]},
        {"username": "ngothihanh",    "display_name": "Ngô Thị Hạnh",    "role": "STUDENT", "faculty": "Khoa Công nghệ thông tin", "major": "Khoa học máy tính",    "year": 4, "interests": ["algorithms", "python", "competitive-programming"]},
        # Sinh viên Kinh tế
        {"username": "vuthimai",      "display_name": "Vũ Thị Mai",      "role": "STUDENT", "faculty": "Khoa Kinh tế",             "major": "Tài chính - Ngân hàng", "year": 3, "interests": ["tai-chinh", "ngan-hang", "chung-khoan"]},
        {"username": "dangvankhanh",  "display_name": "Đặng Văn Khánh",  "role": "STUDENT", "faculty": "Khoa Kinh tế",             "major": "Marketing",             "year": 2, "interests": ["marketing", "thuong-mai-dien-tu", "kinh-te"]},
        {"username": "lythilan",      "display_name": "Lý Thị Lan",      "role": "STUDENT", "faculty": "Khoa Kinh tế",             "major": "Kế toán",               "year": 3, "interests": ["ke-toan", "tai-chinh", "erp"]},
        {"username": "tranvancuong2", "display_name": "Trần Văn Cường",  "role": "STUDENT", "faculty": "Khoa Kinh tế",             "major": "Quản trị kinh doanh",   "year": 4, "interests": ["quan-tri", "startup", "marketing"]},
        # Sinh viên Điện - Điện tử
        {"username": "nguyenthimien", "display_name": "Nguyễn Thị Miên", "role": "STUDENT", "faculty": "Khoa Điện - Điện tử",     "major": "Kỹ thuật điện tử",    "year": 2, "interests": ["arduino", "iot", "vi-dieu-khien", "robot"]},
        {"username": "phanvannam",    "display_name": "Phan Văn Nam",     "role": "STUDENT", "faculty": "Khoa Điện - Điện tử",     "major": "Kỹ thuật điều khiển",  "year": 3, "interests": ["plc", "dieu-khien-pid", "cam-bien"]},
        {"username": "caokhanhoanh",  "display_name": "Cao Khánh Oanh",   "role": "STUDENT", "faculty": "Khoa Điện - Điện tử",     "major": "Kỹ thuật viễn thông",  "year": 3, "interests": ["rf", "vien-thong", "linux"]},
        # Sinh viên Toán
        {"username": "trinhthiphuong","display_name": "Trịnh Thị Phương","role": "STUDENT",  "faculty": "Khoa Toán - Cơ - Tin học","major": "Thống kê",            "year": 3, "interests": ["xac-suat", "thong-ke", "r-language", "machine-learning"]},
        {"username": "maivanquan",    "display_name": "Mai Văn Quân",     "role": "STUDENT", "faculty": "Khoa Toán - Cơ - Tin học", "major": "Toán học",            "year": 2, "interests": ["dai-so-tuyen-tinh", "giai-tich", "toi-uu-hoa"]},
        # Giảng viên CNTT
        {"username": "gsnguyenvanr",  "display_name": "GS. Nguyễn Văn R", "role": "TEACHER", "faculty": "Khoa Công nghệ thông tin", "major": "Khoa học máy tính",   "year": None, "interests": ["ai", "deep-learning", "research", "python", "pytorch"]},
        {"username": "tsnthanhsang",  "display_name": "TS. Nguyễn Thanh Sang", "role": "TEACHER", "faculty": "Khoa Công nghệ thông tin", "major": "Hệ thống thông tin", "year": None, "interests": ["database", "microservices", "docker", "postgresql"]},
        {"username": "thstranh",      "display_name": "ThS. Trần Thị Anh","role": "TEACHER",  "faculty": "Khoa Công nghệ thông tin", "major": "Kỹ thuật phần mềm",  "year": None, "interests": ["java", "spring", "agile", "software-engineering"]},
        {"username": "tslevanu",      "display_name": "TS. Lê Văn Ú",    "role": "TEACHER", "faculty": "Khoa Công nghệ thông tin", "major": "An toàn thông tin",    "year": None, "interests": ["security", "cryptography", "network"]},
        # Giảng viên Kinh tế
        {"username": "gsphamthiv",    "display_name": "GS. Phạm Thị Vân","role": "TEACHER",  "faculty": "Khoa Kinh tế",            "major": "Kinh tế học",          "year": None, "interests": ["kinh-te-vi-mo", "tai-chinh", "phan-tich"]},
        {"username": "tshoangvanw",   "display_name": "TS. Hoàng Văn W",  "role": "TEACHER", "faculty": "Khoa Kinh tế",            "major": "Tài chính - Ngân hàng", "year": None, "interests": ["tai-chinh", "ngan-hang", "fintech"]},
        # Giảng viên Điện - Điện tử
        {"username": "tsdothix",      "display_name": "TS. Đỗ Thị X",    "role": "TEACHER", "faculty": "Khoa Điện - Điện tử",     "major": "Kỹ thuật điện tử",    "year": None, "interests": ["arduino", "iot", "robot", "cam-bien"]},
        # Giảng viên Toán
        {"username": "gsbuitriy",     "display_name": "GS. Bùi Trí Y",   "role": "TEACHER", "faculty": "Khoa Toán - Cơ - Tin học", "major": "Toán ứng dụng",       "year": None, "interests": ["toi-uu-hoa", "xac-suat", "machine-learning", "matlab"]},
        # Sinh viên mới (ít lịch sử — test cold start nhẹ)
        {"username": "svmoi001",      "display_name": "Sinh viên Mới 1",  "role": "STUDENT", "faculty": "Khoa Công nghệ thông tin", "major": "Hệ thống thông tin",  "year": 1, "interests": []},
        {"username": "svmoi002",      "display_name": "Sinh viên Mới 2",  "role": "STUDENT", "faculty": "Khoa Kinh tế",            "major": "Marketing",            "year": 1, "interests": []},
        # Admin
        {"username": "admin001",      "display_name": "Quản trị viên",    "role": "ADMIN",   "faculty": None,                       "major": None,                   "year": None, "interests": []},
        # Extra
        {"username": "user028",       "display_name": "Người dùng 28",    "role": "STUDENT", "faculty": "Khoa Công nghệ thông tin", "major": "Trí tuệ nhân tạo",    "year": 2, "interests": ["ai", "python"]},
        {"username": "user029",       "display_name": "Người dùng 29",    "role": "STUDENT", "faculty": "Khoa Kinh tế",            "major": "Quản trị kinh doanh",   "year": 3, "interests": ["quan-tri", "marketing"]},
    ]

    # Encode user profiles
    profiles_text = []
    for p in user_profiles[:NUM_USERS]:
        parts = [f"Role: {p['role']}"]
        if p.get("faculty"):
            parts.append(f"Faculty: {p['faculty']}")
        if p.get("interests"):
            parts.append(f"Interests: {' '.join(p['interests'])}")
        profiles_text.append(" | ".join(parts))

    logger.info("  ⏳ Encoding %d user profiles ...", len(profiles_text))
    embeddings = model.encode(profiles_text, show_progress_bar=True, batch_size=32)

    # Cold start users (no embedding → triggers cold start path in recommendation)
    cold_start_users = [
        {"user_id": "user-cold-001", "role": "STUDENT", "ab_group": "A",
         "faculty": "Khoa Công nghệ thông tin"},
        {"user_id": "user-cold-002", "role": "STUDENT", "ab_group": "B",
         "faculty": "Khoa Kinh tế"},
    ]

    async with pool.acquire() as conn:
        for i, p in enumerate(user_profiles[:NUM_USERS]):
            user_id = f"user-{i + 1:03d}"
            ab_group = "A" if i % 2 == 0 else "B"
            emb_str = _vector_to_str(embeddings[i])

            await conn.execute(
                """
                INSERT INTO users_profile
                    (user_id, role, faculty, interests, embedding, ab_group, updated_at)
                VALUES ($1, $2, $3, $4, $5::vector(384), $6, NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    role = EXCLUDED.role,
                    faculty = EXCLUDED.faculty,
                    interests = EXCLUDED.interests,
                    embedding = EXCLUDED.embedding,
                    ab_group = EXCLUDED.ab_group,
                    updated_at = NOW()
                """,
                user_id, p["role"],
                p.get("faculty"),
                p.get("interests") or [],
                emb_str, ab_group,
            )

        # Cold start users (no embedding)
        for cu in cold_start_users:
            await conn.execute(
                """
                INSERT INTO users_profile
                    (user_id, role, faculty, ab_group, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (user_id) DO NOTHING
                """,
                cu["user_id"], cu["role"], cu.get("faculty"), cu["ab_group"],
            )

    logger.info("✅ Seeded %d users + %d cold-start users", NUM_USERS, len(cold_start_users))


async def seed_interactions(pool: asyncpg.Pool):
    """Seed 600+ random interactions including all types (view/read/download/buy/bookmark)."""
    logger.info("👆 Seeding %d interactions ...", NUM_INTERACTIONS)

    async with pool.acquire() as conn:
        for _ in range(NUM_INTERACTIONS):
            user_id = f"user-{random.randint(1, NUM_USERS):03d}"
            doc_id = f"doc-{random.randint(1, NUM_DOCUMENTS):04d}"
            interaction_type = random.choice(INTERACTION_TYPES)
            interaction_id = uuid.uuid4()

            await conn.execute(
                """
                INSERT INTO user_interactions (id, user_id, document_id, interaction_type, created_at)
                VALUES ($1, $2, $3, $4, NOW() - ($5 || ' hours')::interval)
                """,
                interaction_id, user_id, doc_id, interaction_type,
                str(random.randint(1, 720)),
            )

    logger.info("✅ Seeded %d interactions", NUM_INTERACTIONS)


# ── pgvector helpers ──────────────────────────────────────────────────
def _vector_to_str(v):
    """Convert numpy array to pgvector text format."""
    if isinstance(v, np.ndarray):
        return "[" + ",".join(str(float(x)) for x in v) + "]"
    return str(v)


async def main():
    logger.info("🌱 Starting data seed (Vietnamese university mock data) ...")

    # 1. Wait for postgres
    await wait_for_postgres()

    # 2. Create database
    await ensure_database()

    # 3. Enable pgvector extension BEFORE creating pool (so type exists)
    raw_conn = await asyncpg.connect(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD,
        database=POSTGRES_DB,
    )
    await raw_conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    await raw_conn.close()
    logger.info("✅ pgvector extension enabled")

    # 4. Create pool with vector codec init
    pool = await asyncpg.create_pool(
        host=POSTGRES_HOST, port=POSTGRES_PORT,
        user=POSTGRES_USER, password=POSTGRES_PASSWORD,
        database=POSTGRES_DB, min_size=2, max_size=5,
    )

    try:
        # 5. Create schema (tables + indexes + migrations)
        await create_schema(pool)

        # 6. Load sentence-transformer model
        logger.info("🧠 Loading sentence-transformer model ...")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("✅ Model loaded: all-MiniLM-L6-v2")

        # 7. Seed data
        await seed_documents(pool, model)
        await seed_users(pool, model)
        await seed_interactions(pool)

        # 8. Rebuild IVFFLAT index after bulk insert
        logger.info("🔧 Rebuilding IVFFLAT index after bulk insert ...")
        async with pool.acquire() as conn:
            await conn.execute("DROP INDEX IF EXISTS idx_documents_embedding_ivfflat")
            await conn.execute("ANALYZE documents")
            await conn.execute("""
                CREATE INDEX idx_documents_embedding_ivfflat
                ON documents USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
        logger.info("✅ IVFFLAT index rebuilt")

        # 9. Verify
        async with pool.acquire() as conn:
            dc = await conn.fetchval("SELECT COUNT(*) FROM documents")
            uc = await conn.fetchval("SELECT COUNT(*) FROM users_profile")
            ic = await conn.fetchval("SELECT COUNT(*) FROM user_interactions")
            faculties = await conn.fetch(
                "SELECT DISTINCT faculty FROM documents WHERE faculty IS NOT NULL LIMIT 10"
            )
            inter_types = await conn.fetch(
                "SELECT interaction_type, COUNT(*) as cnt FROM user_interactions "
                "GROUP BY interaction_type ORDER BY cnt DESC"
            )
            logger.info("📊 Final counts: %d docs, %d users, %d interactions", dc, uc, ic)
            logger.info("🏫 Faculties seeded: %s", [r["faculty"] for r in faculties])
            logger.info("👆 Interaction types: %s", {r["interaction_type"]: r["cnt"] for r in inter_types})

        logger.info("🎉 Seed complete!")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

