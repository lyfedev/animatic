from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = "development"
    aws_region: str = "us-east-1"
    google_cloud_project: str = ""
    google_application_credentials: str = ""
    google_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_image_model: str = "gemini-3.1-flash-image"
    # The daily request cap is per model, not per project
    # (quotaId GenerateRequestsPerDayPerProjectPerModel), so a second TTS
    # model is a real escape hatch when the first one is spent — verified
    # 2026-08-25 against both. Overridable so a run that runs out can finish
    # on the fallback rather than stopping for half a day.
    gemini_tts_model: str = "gemini-3.1-flash-tts-preview"
    gemini_music_model: str = "lyria-3-clip-preview"
    gemini_veo_model: str = "veo-3.1-fast-generate-preview"
    media_bucket: str = "animatic-media-628818"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
