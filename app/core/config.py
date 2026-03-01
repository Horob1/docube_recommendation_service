"""
Application configuration loaded from .env file.
Uses pydantic-settings for type-safe environment variable parsing.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Central configuration for the recommendation service."""

    # ── Eureka Discovery ──────────────────────────────────────────────
    eureka_server: str = Field(
        default="http://localhost:9000/eureka",
        description="Eureka server URL (Spring Cloud Netflix Eureka)",
    )
    service_name: str = Field(default="recommendation-service")
    service_port: int = Field(default=8000)
    service_host: str = Field(default="localhost")

    # ── Kafka ─────────────────────────────────────────────────────────
    kafka_bootstrap_servers: str = Field(default="localhost:7092")
    kafka_group_id: str = Field(default="rm-service-group")
    kafka_auto_offset_reset: str = Field(default="earliest")
    kafka_security_protocol: str = Field(default="SASL_PLAINTEXT")
    kafka_sasl_mechanism: str = Field(default="PLAIN")
    kafka_sasl_username: str = Field(default="horob1")
    kafka_sasl_password: str = Field(default="2410")

    # Kafka Topics
    kafka_topic_documents: str = Field(default="document-events")
    kafka_topic_users: str = Field(default="user-events")
    kafka_topic_recommendations: str = Field(default="recommendation-events")

    # ── PostgreSQL ────────────────────────────────────────────────────
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="horob1_docub_rm_service")
    postgres_user: str = Field(default="postgres")
    postgres_password: str = Field(default="2410")

    # ── Redis ─────────────────────────────────────────────────────────
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_password: str = Field(default="2410")
    redis_db: int = Field(default=5)
    redis_timeout: int = Field(default=5000, description="Redis timeout in ms")
    redis_cache_ttl: int = Field(default=300, description="Cache TTL in seconds")

    # ── ML / ANN ──────────────────────────────────────────────────────
    ann_candidates: int = Field(default=200, description="ANN top-N candidates")
    ann_probes: int = Field(default=10, description="IVFFLAT probes")
    reranker_model_path: str = Field(default="models/reranker.pkl")

    # ── Dev Mode ──────────────────────────────────────────────────────
    dev_mode: bool = Field(
        default=False,
        description="Enable dev-only endpoints (validation, auth, documents, CORS)",
    )
    frontend_url: str = Field(default="http://localhost:3000")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def asyncpg_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn(self) -> str:
        return self.asyncpg_dsn

    @property
    def redis_url(self) -> str:
        return (
            f"redis://:{self.redis_password}@{self.redis_host}"
            f":{self.redis_port}/{self.redis_db}"
        )


# Singleton instance
settings = Settings()
