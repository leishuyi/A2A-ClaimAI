from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./starshield.db"
    debug: bool = True

    class Config:
        env_file = ".env"
        env_prefix = "STARSHIELD_"


settings = Settings()
