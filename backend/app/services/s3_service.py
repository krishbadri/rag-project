import boto3
import os
from botocore.config import Config


def get_s3_client():
    """Get S3 client configured for MinIO or AWS S3"""
    
    # Check if we're using MinIO (local development)
    if os.getenv("S3_ENDPOINT_URL"):
        return boto3.client(
            's3',
            endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://localhost:9000"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY", "minio"),
            aws_secret_access_key=os.getenv("S3_SECRET_KEY", "minio123"),
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'
        )
    else:
        # Use AWS S3
        return boto3.client('s3')


def create_bucket_if_not_exists(bucket_name: str):
    """Create S3 bucket if it doesn't exist"""
    try:
        s3_client = get_s3_client()
        
        try:
            s3_client.head_bucket(Bucket=bucket_name)
        except:
            # Bucket doesn't exist, create it
            s3_client.create_bucket(Bucket=bucket_name)
            
            # If using MinIO, we might need to set bucket policy
            if os.getenv("S3_ENDPOINT_URL"):
                bucket_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": "*"},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                        }
                    ]
                }
                s3_client.put_bucket_policy(Bucket=bucket_name, Policy=str(bucket_policy))
    except Exception as e:
        print(f"Warning: Could not create S3 bucket: {e}")
        print("This is normal if S3/MinIO is not available")


def upload_file(file_path: str, s3_key: str, bucket_name: str = None):
    """Upload file to S3/MinIO"""
    if bucket_name is None:
        bucket_name = os.getenv("S3_BUCKET", "rag-bucket")
    
    s3_client = get_s3_client()
    s3_client.upload_file(file_path, bucket_name, s3_key)


def download_file(s3_key: str, local_path: str, bucket_name: str = None):
    """Download file from S3/MinIO"""
    if bucket_name is None:
        bucket_name = os.getenv("S3_BUCKET", "rag-bucket")
    
    s3_client = get_s3_client()
    s3_client.download_file(bucket_name, s3_key, local_path)


def delete_file(s3_key: str, bucket_name: str = None):
    """Delete file from S3/MinIO"""
    if bucket_name is None:
        bucket_name = os.getenv("S3_BUCKET", "rag-bucket")
    
    s3_client = get_s3_client()
    s3_client.delete_object(Bucket=bucket_name, Key=s3_key)

