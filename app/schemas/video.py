from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class VideoStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    DELETED = "deleted"


# Base schema
class VideoBase(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255,
        strip_whitespace=True
    )


# Used when creating a video
class VideoCreate(VideoBase):
    pass


# Used when returning video information
class VideoResponse(VideoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_user_id: int
    file_path: str
    hls_path: str | None = None
    status: VideoStatus
    upload_date: datetime
    processing_at: datetime | None = None
    finished_at: datetime | None = None
    failure_message: str | None = None