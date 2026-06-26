from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[2]  # ClothingApp/
_BACKEND = Path(__file__).resolve().parents[1]  # ClothingApp/backend/


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://grailseeker:grailseeker@localhost:5432/grailseeker"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    clip_model: str = "ViT-B-32"
    clip_pretrained: str = "openai"
    yolo_weights_path: str = "app/ml/weights/deepfashion2_yolov8s-seg.pt"

    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    ebay_api_url: str = "https://api.ebay.com"
    ebay_auth_url: str = "https://api.ebay.com"

    ingest_interval_minutes: int = 30
    cleanup_hour: int = 3

    guest_daily_limit: int = 5
    user_daily_limit: int = 50

    max_image_size_mb: int = 10
    max_image_dimension: int = 1024

    model_config = SettingsConfigDict(
        env_file=(_ROOT / ".env", _BACKEND / ".env"),
        extra="ignore",
    )


settings = Settings()
