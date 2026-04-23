# ===== AWS S3 Storage Backend Configuration =====
# Complete S3 integration for file uploads and media storage

from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class MediaStorage(S3Boto3Storage):
    """
    S3 storage for user-uploaded media files
    (Videos, images, documents, etc.)
    """
    location = 'media'
    default_acl = 'private'
    file_overwrite = False
    custom_domain = False


class StaticStorage(S3Boto3Storage):
    """
    S3 storage for static files
    (CSS, JS, fonts, etc.)
    """
    location = 'static'
    default_acl = 'public-read'


class CourseContentStorage(S3Boto3Storage):
    """
    Dedicated storage for course content
    (Videos, PDFs, presentations)
    """
    location = 'courses'
    default_acl = 'private'
    file_overwrite = False
    
    def get_accessed_time(self, name):
        """Return the last accessed time (for sorting/cleanup)"""
        return None
    
    def get_created_time(self, name):
        """Return the creation time of the file"""
        return None


class CertificateStorage(S3Boto3Storage):
    """
    Storage for generated certificates
    """
    location = 'certificates'
    default_acl = 'private'
    file_overwrite = False


class S3Manager:
    """
    Advanced S3 operations manager
    Handles uploads, downloads, presigned URLs, and lifecycle management
    """
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    def generate_presigned_url(self, object_key, expiration=3600):
        """
        Generate presigned URL for secure file access
        
        Args:
            object_key: S3 object key (file path)
            expiration: URL expiration time in seconds (default 1 hour)
        
        Returns:
            str: Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': object_key
                },
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            return None
    
    def upload_file(self, file_obj, object_key, metadata=None):
        """
        Upload file to S3
        
        Args:
            file_obj: File object to upload
            object_key: S3 key (path) for the file
            metadata: Optional metadata dict
        
        Returns:
            bool: Success status
        """
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                object_key,
                ExtraArgs=extra_args
            )
            
            logger.info(f"File uploaded successfully: {object_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Error uploading file: {str(e)}")
            return False
    
    def delete_file(self, object_key):
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            logger.info(f"File deleted: {object_key}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False
    
    def copy_file(self, source_key, dest_key):
        """Copy file within S3"""
        try:
            copy_source = {
                'Bucket': self.bucket_name,
                'Key': source_key
            }
            
            self.s3_client.copy_object(
                CopySource=copy_source,
                Bucket=self.bucket_name,
                Key=dest_key
            )
            
            logger.info(f"File copied: {source_key} -> {dest_key}")
            return True
        except ClientError as e:
            logger.error(f"Error copying file: {str(e)}")
            return False
    
    def list_files(self, prefix='', max_keys=100):
        """
        List files in S3 bucket
        
        Args:
            prefix: Filter by prefix (folder path)
            max_keys: Maximum number of keys to return
        
        Returns:
            list: List of file keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
            
        except ClientError as e:
            logger.error(f"Error listing files: {str(e)}")
            return []
    
    def get_file_metadata(self, object_key):
        """Get file metadata from S3"""
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            
            return {
                'size': response['ContentLength'],
                'last_modified': response['LastModified'],
                'content_type': response['ContentType'],
                'metadata': response.get('Metadata', {}),
            }
            
        except ClientError as e:
            logger.error(f"Error getting file metadata: {str(e)}")
            return None
    
    def create_multipart_upload(self, object_key):
        """
        Initiate multipart upload for large files
        
        Returns:
            str: Upload ID
        """
        try:
            response = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_key
            )
            return response['UploadId']
        except ClientError as e:
            logger.error(f"Error creating multipart upload: {str(e)}")
            return None
    
    def generate_presigned_post(self, object_key, expiration=3600, max_size=104857600):
        """
        Generate presigned POST for direct browser uploads
        
        Args:
            object_key: S3 key for the file
            expiration: Expiration time in seconds
            max_size: Maximum file size in bytes (default 100MB)
        
        Returns:
            dict: URL and fields for POST request
        """
        try:
            conditions = [
                {'bucket': self.bucket_name},
                ['starts-with', '$key', object_key],
                ['content-length-range', 0, max_size]
            ]
            
            response = self.s3_client.generate_presigned_post(
                Bucket=self.bucket_name,
                Key=object_key,
                Conditions=conditions,
                ExpiresIn=expiration
            )
            
            return response
            
        except ClientError as e:
            logger.error(f"Error generating presigned POST: {str(e)}")
            return None


class VideoTranscoder:
    """
    Handle video transcoding using AWS Elastic Transcoder or MediaConvert
    """
    
    def __init__(self):
        self.transcoder = boto3.client(
            'elastictranscoder',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
    
    def transcode_video(self, input_key, output_key_prefix, pipeline_id):
        """
        Transcode video to multiple formats/qualities
        
        Args:
            input_key: Input video S3 key
            output_key_prefix: Prefix for output files
            pipeline_id: Elastic Transcoder pipeline ID
        
        Returns:
            str: Job ID
        """
        try:
            # Example: Create transcoding job
            # You'll need to configure presets for different qualities
            response = self.transcoder.create_job(
                PipelineId=pipeline_id,
                Input={
                    'Key': input_key,
                },
                Outputs=[
                    {
                        'Key': f"{output_key_prefix}_1080p.mp4",
                        'PresetId': '1351620000001-000001',  # System preset for 1080p
                    },
                    {
                        'Key': f"{output_key_prefix}_720p.mp4",
                        'PresetId': '1351620000001-000010',  # System preset for 720p
                    },
                    {
                        'Key': f"{output_key_prefix}_480p.mp4",
                        'PresetId': '1351620000001-000020',  # System preset for 480p
                    },
                ]
            )
            
            job_id = response['Job']['Id']
            logger.info(f"Transcoding job created: {job_id}")
            return job_id
            
        except ClientError as e:
            logger.error(f"Error creating transcoding job: {str(e)}")
            return None


class CDNManager:
    """
    CloudFront CDN management for fast content delivery
    """
    
    def __init__(self):
        self.cloudfront = boto3.client(
            'cloudfront',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        self.distribution_id = getattr(settings, 'AWS_CLOUDFRONT_DISTRIBUTION_ID', None)
    
    def create_invalidation(self, paths):
        """
        Invalidate CloudFront cache for specific paths
        
        Args:
            paths: List of paths to invalidate (e.g., ['/media/video.mp4'])
        
        Returns:
            str: Invalidation ID
        """
        if not self.distribution_id:
            logger.warning("CloudFront distribution ID not configured")
            return None
        
        try:
            import uuid
            
            response = self.cloudfront.create_invalidation(
                DistributionId=self.distribution_id,
                InvalidationBatch={
                    'Paths': {
                        'Quantity': len(paths),
                        'Items': paths
                    },
                    'CallerReference': str(uuid.uuid4())
                }
            )
            
            invalidation_id = response['Invalidation']['Id']
            logger.info(f"CloudFront invalidation created: {invalidation_id}")
            return invalidation_id
            
        except ClientError as e:
            logger.error(f"Error creating invalidation: {str(e)}")
            return None
