"""
Auto Seed Script — populates the database with real test data.

Uses sentence-transformers to generate REAL embeddings.
Seeds: 200 documents, 30 users, 500+ interactions.

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
NUM_INTERACTIONS = 500
EMBEDDING_DIM = 384

# ── Document Templates ────────────────────────────────────────────────
CATEGORIES = {
    "Machine Learning": {
        "tags": ["ml", "ai", "deep-learning", "neural-networks", "sklearn"],
        "topics": [
            "Introduction to Machine Learning Algorithms",
            "Supervised Learning: Classification and Regression",
            "Unsupervised Learning: Clustering and Dimensionality Reduction",
            "Ensemble Methods: Random Forests and Gradient Boosting",
            "Feature Engineering Best Practices",
            "Cross-Validation and Model Selection",
            "Hyperparameter Tuning with Grid Search",
            "Introduction to AutoML",
            "Transfer Learning Fundamentals",
            "Reinforcement Learning Basics",
            "Bayesian Machine Learning",
            "Online Learning and Streaming Data",
        ],
    },
    "Deep Learning": {
        "tags": ["deep-learning", "pytorch", "tensorflow", "cnn", "rnn", "transformer"],
        "topics": [
            "Convolutional Neural Networks for Image Classification",
            "Recurrent Neural Networks and LSTM",
            "Transformers and Attention Mechanisms",
            "Generative Adversarial Networks",
            "Autoencoders and Variational Autoencoders",
            "Object Detection with YOLO",
            "Semantic Segmentation",
            "Neural Style Transfer",
            "Graph Neural Networks",
            "Neural Architecture Search",
            "Knowledge Distillation",
            "Self-Supervised Learning",
        ],
    },
    "Natural Language Processing": {
        "tags": ["nlp", "text", "bert", "gpt", "tokenization"],
        "topics": [
            "Text Preprocessing and Tokenization",
            "Word Embeddings: Word2Vec and GloVe",
            "BERT: Pre-trained Language Models",
            "Sentiment Analysis with Transformers",
            "Named Entity Recognition",
            "Machine Translation",
            "Text Summarization",
            "Question Answering Systems",
            "Topic Modeling with LDA",
            "Text Generation with GPT",
        ],
    },
    "Python Programming": {
        "tags": ["python", "programming", "oop", "async", "typing"],
        "topics": [
            "Advanced Python: Decorators and Metaclasses",
            "Async/Await: Concurrency in Python",
            "Python Type Hints and Mypy",
            "Design Patterns in Python",
            "Python Performance Optimization",
            "Testing with Pytest",
            "Python Packaging and Distribution",
            "Functional Programming in Python",
            "Python Memory Management",
            "Context Managers and Generators",
        ],
    },
    "Web Development": {
        "tags": ["web", "fastapi", "django", "rest", "api", "microservices"],
        "topics": [
            "Building REST APIs with FastAPI",
            "Django ORM Deep Dive",
            "Microservices Architecture Patterns",
            "API Gateway Design",
            "WebSocket Real-time Communication",
            "GraphQL vs REST",
            "Authentication and OAuth 2.0",
            "Rate Limiting and Throttling",
            "API Versioning Strategies",
            "Server-Sent Events",
        ],
    },
    "Data Engineering": {
        "tags": ["data-engineering", "etl", "pipeline", "spark", "kafka"],
        "topics": [
            "Building Data Pipelines with Apache Kafka",
            "Apache Spark for Big Data Processing",
            "ETL Best Practices",
            "Data Warehouse Design",
            "Stream Processing with Flink",
            "Data Lake Architecture",
            "Schema Evolution and Versioning",
            "Data Quality Monitoring",
            "CDC with Debezium",
            "Batch vs Stream Processing",
        ],
    },
    "DevOps": {
        "tags": ["devops", "docker", "kubernetes", "ci-cd", "cloud"],
        "topics": [
            "Docker: Containerization Fundamentals",
            "Kubernetes in Production",
            "CI/CD Pipelines with GitHub Actions",
            "Infrastructure as Code with Terraform",
            "Monitoring with Prometheus and Grafana",
            "Log Management with ELK Stack",
            "Service Mesh with Istio",
            "GitOps Workflow",
            "Cloud-Native Architecture",
            "Chaos Engineering",
        ],
    },
    "Database": {
        "tags": ["database", "sql", "nosql", "postgres", "redis", "vector-db"],
        "topics": [
            "PostgreSQL Advanced Queries",
            "Redis Caching Strategies",
            "MongoDB Aggregation Framework",
            "Database Indexing and Optimization",
            "Sharding and Partitioning",
            "Vector Databases and pgvector",
            "Time-Series Databases",
            "Graph Databases with Neo4j",
            "Database Migration Strategies",
            "Connection Pooling and Performance",
        ],
    },
    "System Design": {
        "tags": ["system-design", "architecture", "distributed", "scalability"],
        "topics": [
            "Designing a URL Shortener",
            "Building a Real-time Chat System",
            "Distributed Caching Strategies",
            "Load Balancing Algorithms",
            "Message Queue Patterns",
            "CAP Theorem and Consistency Models",
            "Event-Driven Architecture",
            "CQRS and Event Sourcing",
            "Rate Limiter Design",
            "Search Engine Architecture",
        ],
    },
    "Security": {
        "tags": ["security", "encryption", "auth", "jwt", "oauth"],
        "topics": [
            "JWT Authentication Deep Dive",
            "OAuth 2.0 and OpenID Connect",
            "API Security Best Practices",
            "SQL Injection Prevention",
            "Cross-Site Scripting (XSS) Defense",
            "Encryption at Rest and in Transit",
            "Security Headers and CORS",
            "Penetration Testing Basics",
        ],
    },
}

ROLES = ["STUDENT", "TEACHER"]
LANGUAGES = ["en", "en", "en", "vi"]  # weighted towards English
INTERACTION_TYPES = ["view", "view", "view", "download", "bookmark", "buy"]  # weighted


def _generate_description(title: str, category: str) -> str:
    return f"A comprehensive guide to {title.lower()}. Covers key concepts in {category} with practical examples and real-world applications."


def _generate_content(title: str, category: str) -> str:
    return (
        f"{title} is an important topic in {category}. "
        f"This document covers the fundamentals, advanced techniques, and "
        f"real-world use cases. Whether you're a beginner or an experienced "
        f"practitioner, this guide provides valuable insights and hands-on "
        f"examples to help you master the subject. The content has been "
        f"carefully curated from industry experts and academic research. "
        f"Topics include theory, implementation, best practices, and common "
        f"pitfalls to avoid."
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

    all_topics = []
    for cat_name, cat_data in CATEGORIES.items():
        for topic in cat_data["topics"]:
            all_topics.append((cat_name, topic, cat_data["tags"]))

    # Repeat/cycle to reach NUM_DOCUMENTS
    docs = []
    for i in range(NUM_DOCUMENTS):
        idx = i % len(all_topics)
        cat_name, title, cat_tags = all_topics[idx]

        # Add variant suffix to make titles unique
        if i >= len(all_topics):
            title = f"{title} (Part {i // len(all_topics) + 1})"

        doc_id = f"doc-{i + 1:04d}"
        tags = random.sample(cat_tags, min(3, len(cat_tags)))
        categories = [cat_name.lower().replace(" ", "-")]
        language = random.choice(LANGUAGES)
        author_id = f"author-{random.randint(1, 10):02d}"
        author_role = random.choice(ROLES)
        description = _generate_description(title, cat_name)
        content = _generate_content(title, cat_name)
        popularity = round(random.uniform(0, 200), 1)

        # Build combined text for embedding
        combined = f"Title: {title}\nDescription: {description}\nTags: {' '.join(tags)}\nCategories: {' '.join(categories)}\nContent: {content[:500]}"

        docs.append({
            "document_id": doc_id,
            "title": title,
            "description": description,
            "content": content,
            "tags": tags,
            "categories": categories,
            "language": language,
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


    # Batch insert — pass embeddings as text, cast in SQL
    async with pool.acquire() as conn:
        for i, doc in enumerate(docs):
            emb_str = _vector_to_str(embeddings[i])
            await conn.execute(
                """
                INSERT INTO documents (
                    document_id, title, description, content,
                    tags, categories, language,
                    author_id, author_role, embedding,
                    popularity_score, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::vector(384),$11, NOW() - ($12 || ' days')::interval)
                ON CONFLICT (document_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    embedding = EXCLUDED.embedding,
                    updated_at = EXCLUDED.updated_at
                """,
                doc["document_id"], doc["title"], doc["description"],
                doc["content"], doc["tags"], doc["categories"],
                doc["language"], doc["author_id"], doc["author_role"],
                emb_str, doc["popularity_score"],
                str(random.randint(1, 90)),
            )

    logger.info("✅ Seeded %d documents", NUM_DOCUMENTS)


async def seed_users(pool: asyncpg.Pool, model):
    """Seed 30 users with embeddings and random A/B groups."""
    logger.info("👤 Seeding %d users ...", NUM_USERS)

    interest_pools = {
        "ml_enthusiast": "machine learning deep learning neural networks pytorch tensorflow",
        "web_developer": "web development api fastapi django microservices cloud",
        "data_engineer": "data engineering kafka spark etl pipeline stream processing",
        "devops_pro": "devops docker kubernetes ci-cd infrastructure cloud-native",
        "nlp_researcher": "natural language processing text transformers bert gpt sentiment",
        "db_admin": "database postgresql redis mongodb indexing optimization sharding",
        "security_expert": "security encryption authentication jwt oauth api-security",
        "system_architect": "system design architecture distributed scalability caching",
        "python_dev": "python programming async decorators testing packaging oop",
        "full_stack": "web api database python javascript react frontend backend",
    }

    profiles = list(interest_pools.keys())

    users = []
    for i in range(NUM_USERS):
        user_id = f"user-{i + 1:03d}"
        role = random.choice(ROLES)
        ab_group = "A" if i % 2 == 0 else "B"
        profile_type = profiles[i % len(profiles)]
        interest_text = interest_pools[profile_type]

        combined = f"User profile: {profile_type}. Interests: {interest_text}. Role: {role}"

        users.append({
            "user_id": user_id,
            "role": role,
            "ab_group": ab_group,
            "combined_text": combined,
        })

    # Also create 2 cold-start users (no embedding)
    cold_start_users = [
        {"user_id": "user-cold-001", "role": "STUDENT", "ab_group": "A"},
        {"user_id": "user-cold-002", "role": "STUDENT", "ab_group": "B"},
    ]

    # Encode user profiles
    texts = [u["combined_text"] for u in users]
    logger.info("  ⏳ Encoding %d user profiles ...", len(texts))
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)

    async with pool.acquire() as conn:
        for i, user in enumerate(users):
            emb_str = _vector_to_str(embeddings[i])
            await conn.execute(
                """
                INSERT INTO users_profile (user_id, role, ab_group, embedding, updated_at)
                VALUES ($1, $2, $3, $4::vector(384), NOW())
                ON CONFLICT (user_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    ab_group = EXCLUDED.ab_group,
                    updated_at = NOW()
                """,
                user["user_id"], user["role"], user["ab_group"], emb_str,
            )

        # Cold start users (no embedding)
        for cu in cold_start_users:
            await conn.execute(
                """
                INSERT INTO users_profile (user_id, role, ab_group, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (user_id) DO NOTHING
                """,
                cu["user_id"], cu["role"], cu["ab_group"],
            )

    logger.info("✅ Seeded %d users + %d cold-start users", NUM_USERS, len(cold_start_users))


async def seed_interactions(pool: asyncpg.Pool):
    """Seed 500+ random interactions."""
    logger.info("👆 Seeding %d interactions ...", NUM_INTERACTIONS)

    async with pool.acquire() as conn:
        for _ in range(NUM_INTERACTIONS):
            user_id = f"user-{random.randint(1, NUM_USERS):03d}"
            doc_id = f"doc-{random.randint(1, NUM_DOCUMENTS):04d}"
            interaction_type = random.choice(INTERACTION_TYPES)
            interaction_id = str(uuid.uuid4())

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
    logger.info("🌱 Starting data seed ...")

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
        # 5. Create schema (tables + indexes)
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
            logger.info("📊 Final counts: %d docs, %d users, %d interactions", dc, uc, ic)

        logger.info("🎉 Seed complete!")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

