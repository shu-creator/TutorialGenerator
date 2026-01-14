"""Storage service for S3/MinIO."""
import io
import os
from functools import lru_cache
from typing import Optional, BinaryIO
import zipfile

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import StorageError

logger = get_logger(__name__)


class StorageService:
    """S3/MinIO storage service."""

    def __init__(self):
        settings = get_settings()
        self.bucket = settings.s3_bucket
        self.endpoint_url = settings.s3_endpoint_url

        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=Config(signature_version="s3v4"),
        )

    def upload_file(
        self,
        file_obj: BinaryIO,
        key: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Upload a file to storage.

        Args:
            file_obj: File-like object to upload
            key: S3 key (path)
            content_type: Optional content type

        Returns:
            The S3 URI of the uploaded file
        """
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            self.client.upload_fileobj(
                file_obj,
                self.bucket,
                key,
                ExtraArgs=extra_args if extra_args else None
            )

            uri = f"s3://{self.bucket}/{key}"
            logger.info(f"Uploaded file to {key}")
            return uri

        except ClientError as e:
            logger.error(f"Failed to upload file to {key}: {e}")
            raise StorageError(f"Failed to upload file: {e}")

    def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: Optional[str] = None
    ) -> str:
        """Upload bytes to storage."""
        return self.upload_file(io.BytesIO(data), key, content_type)

    def download_file(self, key: str, local_path: str) -> str:
        """
        Download a file from storage to local path.

        Args:
            key: S3 key (path)
            local_path: Local file path to save to

        Returns:
            The local file path
        """
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.client.download_file(self.bucket, key, local_path)
            logger.info(f"Downloaded {key} to {local_path}")
            return local_path

        except ClientError as e:
            logger.error(f"Failed to download file {key}: {e}")
            raise StorageError(f"Failed to download file: {e}")

    def download_bytes(self, key: str) -> bytes:
        """Download file content as bytes."""
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to download file {key}: {e}")
            raise StorageError(f"Failed to download file: {e}")

    def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        response_content_type: Optional[str] = None,
        response_content_disposition: Optional[str] = None
    ) -> str:
        """
        Generate a presigned URL for downloading a file.

        Args:
            key: S3 key (path)
            expires_in: URL expiration time in seconds
            response_content_type: Override content type in response
            response_content_disposition: Set content disposition header

        Returns:
            Presigned URL
        """
        try:
            params = {
                "Bucket": self.bucket,
                "Key": key,
            }

            if response_content_type:
                params["ResponseContentType"] = response_content_type
            if response_content_disposition:
                params["ResponseContentDisposition"] = response_content_disposition

            url = self.client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in
            )

            # Replace internal docker hostname with localhost for local dev
            if "minio:9000" in url:
                url = url.replace("minio:9000", "localhost:9000")

            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {key}: {e}")
            raise StorageError(f"Failed to generate presigned URL: {e}")

    def list_objects(self, prefix: str) -> list[dict]:
        """List objects with given prefix."""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            return response.get("Contents", [])
        except ClientError as e:
            logger.error(f"Failed to list objects with prefix {prefix}: {e}")
            raise StorageError(f"Failed to list objects: {e}")

    def delete_object(self, key: str) -> None:
        """Delete an object."""
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"Deleted object {key}")
        except ClientError as e:
            logger.error(f"Failed to delete object {key}: {e}")
            raise StorageError(f"Failed to delete object: {e}")

    def create_frames_zip(self, job_id: str, frames_prefix: str) -> str:
        """
        Create a zip file containing all frames for a job.

        Args:
            job_id: Job ID
            frames_prefix: S3 prefix for frames

        Returns:
            S3 key of the zip file
        """
        try:
            objects = self.list_objects(frames_prefix)
            if not objects:
                raise StorageError("No frames found to zip")

            # Create zip in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for obj in objects:
                    key = obj["Key"]
                    filename = os.path.basename(key)
                    if filename.endswith(".png") or filename.endswith(".jpg"):
                        content = self.download_bytes(key)
                        zf.writestr(filename, content)

            zip_buffer.seek(0)

            # Upload zip
            zip_key = f"jobs/{job_id}/frames.zip"
            self.upload_file(zip_buffer, zip_key, "application/zip")

            return zip_key

        except Exception as e:
            logger.error(f"Failed to create frames zip for job {job_id}: {e}")
            raise StorageError(f"Failed to create frames zip: {e}")

    def key_from_uri(self, uri: str) -> str:
        """Extract S3 key from URI."""
        if uri.startswith("s3://"):
            # s3://bucket/key -> key
            parts = uri[5:].split("/", 1)
            return parts[1] if len(parts) > 1 else ""
        return uri


@lru_cache()
def get_storage_service() -> StorageService:
    """Get cached storage service instance."""
    return StorageService()
