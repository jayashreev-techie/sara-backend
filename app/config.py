"""Application configuration loaded from .env"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "sara_fabrication"

    # JWT
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 30

    # OTP
    OTP_MODE: str = "test"  # test | production
    OTP_EXPIRE_MINUTES: int = 5
    MSG91_AUTH_KEY: str = ""
    MSG91_TEMPLATE_ID: str = ""
    MSG91_SENDER_ID: str = "SARAFB"

    # Super Admin (hardcoded credentials — stored in .env only)
    SUPER_ADMIN_EMAIL: str = "superadmin@sara.com"
    SUPER_ADMIN_PASSWORD: str = "SuperAdmin@123"

    # App
    APP_ENV: str = "development"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    DB_SSLMODE: str = "prefer"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?sslmode={self.DB_SSLMODE}"
        )


settings = Settings()
