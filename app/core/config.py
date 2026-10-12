from decimal import Decimal
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Credit Card Payment System - FastAPI Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_NAME: str = "credit_card_db"
    DB_USER: str = "root"
    DB_PASSWORD: str = "Charan123"
    DATABASE_URL: str = ""

    JWT_SECRET_KEY: str = "change-me"
    CARD_ENCRYPTION_KEY: str = "bH0KzQalnJeGNWEA4MgUYpHRX2r9G3mDUCfI2hCeYvU="
    INTERNAL_API_KEY: str = "INTERNAL_API_KEY=your-generated-secret-key-here"

    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_MINUTES: int = 30
    JWT_REFRESH_DAYS: int = 1
    PASSWORD_HASH_ITERATIONS: int = 1_000_000

    DEFAULT_CREDIT_LIMIT: Decimal = Decimal("100000.00")
    MAX_SINGLE_PAYMENT: Decimal = Decimal("200000.00")

    FRAUD_WINDOW_MINUTES: int = 5
    FRAUD_MAX_PAYMENTS_IN_WINDOW: int = 5
    FRAUD_HIGH_AMOUNT: Decimal = Decimal("100000.00")
    FRAUD_DECLINE_SCORE: int = 70

    LOGIN_RATE_LIMIT_PER_MINUTE: int = 5
    PAYMENT_RATE_LIMIT_PER_MINUTE: int = 20

    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        password = quote_plus(self.DB_PASSWORD)
        return (
            f"mysql+pymysql://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/"
            f"{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
