from app.core.config import settings
import mimetypes
import boto3
from pathlib import Path
import shutil
from fastapi import UploadFile


class LocalStorage:

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)

    async def save(self, file: UploadFile, filename: str, directory: str) -> str:

        target_dir = self.base_dir / directory
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / filename

        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return str(file_path)


class S3Storage:

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="test",
            region_name="us-east-1",
        )

        self.bucket = "videos"

    def upload_file(self, file: UploadFile, object_key: str):
        self.client.upload_fileobj(
            file.file,
            self.bucket,
            object_key,
            ExtraArgs={
                "ContentType": file.content_type or "application/octet-stream"
            }
        )

    def delete_file(self, object_key: str):
        self.client.delete_object(
            Bucket=self.bucket,
            Key=object_key
        )

    def download_file(self, object_key: str, destination: str):
        self.client.download_file(
            self.bucket,
            object_key,
            destination
        )
    def upload_local_file(self, local_path: str, object_key: str):
            content_type, _ = mimetypes.guess_type(local_path)

            self.client.upload_file(
                local_path,
                self.bucket,
                object_key,
                ExtraArgs={
                    "ContentType": content_type or "application/octet-stream"
                }
        )
    def generate_presigned_url(
        self,
        object_key: str,
        expires_in: int = 30
    ):
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": object_key
            },
            ExpiresIn=expires_in
        )


    def get_object(self, object_key: str):
        return self.client.get_object(
            Bucket=self.bucket,
            Key=object_key
        )

        
storage = S3Storage()