from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    aws_region: str = "us-east-1"
    google_cloud_project: str = ""
    google_application_credentials: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
