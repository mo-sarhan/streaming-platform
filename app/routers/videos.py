from fastapi.responses import StreamingResponse
from fastapi import HTTPException
import mimetypes
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.video import Video, VideoStatus
from app.schemas.video import VideoCreate, VideoResponse
from app.services.storage import storage
from app.tasks.video import process_video


router = APIRouter(
    prefix="/videos",
    tags=["Videos"]
)


@router.post("/upload", response_model=VideoResponse)
def upload_video(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # 1. Validate title
    try:
        video_data = VideoCreate(title=title)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        )

    # 2. Validate file type (basic check)
    if file.content_type != "video/mp4":
        raise HTTPException(
            status_code=400,
            detail="Only MP4 videos are supported"
        )

    # 3. Generate unique object key
    unique_id = uuid4().hex
    object_key = f"originals/{unique_id}/original.mp4"

    # 4. Upload original video to S3
    try:
        storage.upload_file(file, object_key)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to upload video"
        )

    # 5. Save metadata in PostgreSQL
    try:
        video = Video(
            title=video_data.title,
            file_path=object_key,
            hls_path=None,
            status=VideoStatus.PENDING,
            upload_user_id=1,  # Temporary until authentication is connected
        )

        db.add(video)
        db.commit()
        db.refresh(video)
        process_video.delay(video.id)

    except Exception as e:
        print(e)
        db.rollback()

        # Avoid leaving an orphaned object in S3
        storage.delete_file(object_key)

        raise HTTPException(
            status_code=500,
            detail="Failed to save video metadata"
        )

    return video


@router.get("/{video_id}/play")
def get_video_playback(
    video_id: int,
    db: Session = Depends(get_db)
):
    video = db.query(Video).filter(
        Video.id == video_id
    ).first()

    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    if video.status != VideoStatus.SUCCESS:
        raise HTTPException(
            status_code=409,
            detail="Video is not ready for playback"
        )

    master_key = f"{video.hls_path}master.m3u8"

    playback_url = storage.generate_presigned_url(
        master_key
    )

    return {
        "video_id": video.id,
        "title": video.title,
        "playback_url": playback_url
    }


@router.get("/{video_id}/hls/{object_path:path}")
def get_hls_file(
    video_id: int,
    object_path: str,
    db: Session = Depends(get_db)
):
    video = db.query(Video).filter(
        Video.id == video_id
    ).first()

    if not video:
        raise HTTPException(404, "Video not found")

    if video.status != VideoStatus.SUCCESS or not video.hls_path:
        raise HTTPException(409, "Video is not ready")

    # Prevent path traversal
    parts = object_path.split("/")

    if any(part in ("..", ".") for part in parts):
        raise HTTPException(400, "Invalid object path")

    object_key = f"{video.hls_path}{object_path}"

    try:
        response = storage.get_object(object_key)
    except Exception:
        raise HTTPException(404, "HLS file not found")

    body = response["Body"]

    def stream():
        try:
            while chunk := body.read(1024 * 1024):
                yield chunk
        finally:
            body.close()

    content_type = (
        "application/vnd.apple.mpegurl"
        if object_path.endswith(".m3u8")
        else "video/mp2t"
        if object_path.endswith(".ts")
        else mimetypes.guess_type(object_path)[0]
        or "application/octet-stream"
    )

    return StreamingResponse(
        stream(),
        media_type=content_type
    )
