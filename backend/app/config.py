from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://grailseeker:grailseeker@localhost:5432/grailseeker"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    clip_model: str = "ViT-B-32"
    clip_pretrained: str = "openai"
    yolo_weights_path: str = "app/ml/weights/yolov8_fashion.pt"

    scrape_interval_minutes: int = 30
    scrape_delay_seconds: int = 2
    cleanup_hour: int = 3

    guest_daily_limit: int = 5
    user_daily_limit: int = 50

    max_image_size_mb: int = 10
    max_image_dimension: int = 1024

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
