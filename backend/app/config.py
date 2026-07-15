from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[2]  # ClothingApp/
_BACKEND = Path(__file__).resolve().parents[1]  # ClothingApp/backend/


class Settings(BaseSettings):
    # "production" disables /docs + /openapi.json and stops trusting
    # X-Forwarded-For for guest rate-limit keys (only CF-Connecting-IP,
    # which Cloudflare overwrites, is spoof-proof behind the tunnel).
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://grailseeker:grailseeker@localhost:5432/grailseeker"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    # Server-only admin key; required for account deletion (App Store
    # guideline 5.1.1(v)). NEVER ship this to the mobile app.
    supabase_service_role_key: str = ""

    # Loopback only: the Cloudflare tunnel connects to localhost, so the API
    # never needs to listen on the LAN.
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # Native apps send no Origin header, so CORS only affects browser clients
    # (Expo web / dev tools).
    cors_origins: list[str] = [
        "http://localhost:8081",
        "http://localhost:19006",
    ]

    # -quickgelu variant matches the activation the OpenAI weights were trained
    # with; plain ViT-B-32 + openai tag silently degrades embedding quality
    clip_model: str = "ViT-B-32-quickgelu"
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
    # /find is unmetered for users (PRD §4.5: 1 upload = 1 search, metered at
    # /segment), but a generous per-caller daily cap stops GPU-burn abuse.
    find_daily_limit: int = 200

    # /listings/{id}/check hits the eBay getItem API; within this TTL the
    # stored is_active is returned instead (eBay call budget, PRD §7.3).
    listing_check_ttl_minutes: int = 15

    max_image_size_mb: int = 10
    max_image_dimension: int = 1024
    # Reject before full decode: a small file can decompress to a huge bitmap.
    max_image_pixels: int = 40_000_000

    rate_limit_retention_days: int = 7

    model_config = SettingsConfigDict(
        env_file=(_ROOT / ".env", _BACKEND / ".env"),
        extra="ignore",
    )


settings = Settings()
