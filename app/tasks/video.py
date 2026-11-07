import os
import tempfile
import logging

from datetime import datetime, timezone

from sqlalchemy import update

from app.celery_app import celery_app
from app.db.database import SessionLocal

from app.models.video import Video, VideoStatus

from app.services.storage import storage

from app.services.transcoder import (
    transcode_video,
    create_master_playlist,
)


logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="process_video",
    max_retries=2,
)
def process_video(self, video_id: int):

    db = SessionLocal()

    uploaded_keys = []

    try:

        # ----------------------------------
        # 1. Atomically claim the video
        # ----------------------------------

        result = db.execute(
            update(Video)
            .where(
                Video.id == video_id,
                Video.status == VideoStatus.PENDING
            )
            .values(
                status=VideoStatus.PROCESSING,
                processing_at=datetime.now(timezone.utc),
                failure_message=None,
            )
        )

        db.commit()

        if result.rowcount == 0:
            logger.info(
                "Video %s is not pending or does not exist",
                video_id
            )
            return

        video = db.get(Video, video_id)

        # ----------------------------------
        # 2. Create temporary workspace
        # ----------------------------------

        with tempfile.TemporaryDirectory(
            prefix=f"video_{video_id}_"
        ) as temp_dir:

            original_path = os.path.join(
                temp_dir,
                "original.mp4"
            )

            output_dir = os.path.join(
                temp_dir,
                "hls"
            )

            os.makedirs(output_dir)

            # ----------------------------------
            # 3. Download original from S3
            # ----------------------------------

            storage.download_file(
                video.file_path,
                original_path
            )

            logger.info(
                "Downloaded original video %s",
                video_id
            )

            # ----------------------------------
            # 4. Transcode into HLS
            # ----------------------------------

            renditions = transcode_video(
                original_path,
                output_dir
            )

            # ----------------------------------
            # 5. Generate master playlist
            # ----------------------------------

            create_master_playlist(
                output_dir,
                renditions
            )

            # ----------------------------------
            # 6. Upload HLS files to S3
            # ----------------------------------

            hls_prefix = f"hls/{video_id}/"

            for root, dirs, files in os.walk(output_dir):

                for filename in files:

                    local_path = os.path.join(
                        root,
                        filename
                    )

                    relative_path = os.path.relpath(
                        local_path,
                        output_dir
                    )

                    object_key = (
                        hls_prefix + relative_path
                    )

                    storage.upload_local_file(
                        local_path,
                        object_key
                    )

                    uploaded_keys.append(object_key)

                    logger.info(
                        "Uploaded %s",
                        object_key
                    )

        # ----------------------------------
        # 7. Mark video as SUCCESS
        # ----------------------------------

        video = db.get(Video, video_id)

        video.hls_path = f"hls/{video_id}/"
        video.status = VideoStatus.SUCCESS
        video.finished_at = datetime.now(timezone.utc)
        video.failure_message = None

        db.commit()

        logger.info(
            "Video %s processed successfully",
            video_id
        )

        return {
            "video_id": video_id,
            "status": "success",
            "hls_path": video.hls_path,
        }

    except Exception as exc:

        db.rollback()

        logger.exception(
            "Failed to process video %s",
            video_id
        )

        # ----------------------------------
        # 8. Clean up partially uploaded HLS
        # ----------------------------------

        for object_key in uploaded_keys:

            try:
                storage.delete_file(object_key)

            except Exception:
                logger.exception(
                    "Failed to delete S3 object %s",
                    object_key
                )

        # ----------------------------------
        # 9. Mark video as FAILED
        # ----------------------------------

        try:

            db.execute(
                update(Video)
                .where(
                    Video.id == video_id,
                    Video.status == VideoStatus.PROCESSING
                )
                .values(
                    status=VideoStatus.FAILED,
                    failure_message=str(exc)[:4000],
                    finished_at=datetime.now(timezone.utc),
                )
            )

            db.commit()

        except Exception:
            db.rollback()
            logger.exception(
                "Could not update video failure status"
            )

        raise

    finally:
        db.close()