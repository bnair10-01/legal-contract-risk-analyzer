from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str
    database_url: str = "postgresql://postgres:secret@localhost:5432/legalagent"
    reports_dir: str = "/reports"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
