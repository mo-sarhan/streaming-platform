import enum
from app.db.base import Base
from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column,relationship


class VideoStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    DELETED = "deleted"


class Video(Base):
    __tablename__ = "videos"

    __table_args__ = (
        CheckConstraint(
            "length(trim(title)) > 0",
            name="title_not_empty"
        ),
        CheckConstraint(
            "length(trim(file_path)) > 0",
            name="file_path_not_empty"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,index=True
    )

    upload_user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id"),
        nullable=False
    )

    uploader: Mapped["User"] = relationship(
        back_populates="videos"
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True
    )
    hls_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=True,
        unique=True
    )

    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus, name="video_status"),
        default=VideoStatus.PENDING,
        nullable=False,
        index=True
    )

    processing_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    failure_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    retry_count: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False
    )

    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )