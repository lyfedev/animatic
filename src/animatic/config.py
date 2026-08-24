from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    aws_region: str = "us-east-1"
    google_cloud_project: str = ""
    google_application_credentials: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_image_model: str = "gemini-3.1-flash-image"
    media_bucket: str = "animatic-media-628818"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
