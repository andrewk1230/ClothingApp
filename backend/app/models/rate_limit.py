import uuid
from datetime import date

from sqlalchemy import Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.listing import Base


class RateLimit(Base):
    __tablename__ = "rate_limits"
    __table_args__ = (UniqueConstraint("key", "window_date"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(255))
    key_type: Mapped[str] = mapped_column(String(10))
    search_count: Mapped[int] = mapped_column(Integer, default=0)
    window_date: Mapped[date] = mapped_column(Date, default=date.today)
