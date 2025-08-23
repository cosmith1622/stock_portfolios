import os
import logging
import boto3
from botocore.exceptions import ClientError

class s3_connector:
    def __init__(self):
        self.s3_client = boto3.client('s3')

    def create_bucket(self,bucket_name, region=None):
        """Create an S3 bucket in a specified region

        If a region is not specified, the bucket is created in the S3 default
        region (us-east-1).

        :param bucket_name: Bucket to create
        :param region: String region to create bucket in, e.g., 'us-west-2'
        :return: True if bucket created, else False
        """

        # Create bucket
        try:
            if region is None:
                #s3_client = boto3.client('s3')
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.region_name = region
                #s3_client = boto3.client('s3', region_name=region)
                location = {'LocationConstraint': region}
                self.s3_client.create_bucket(Bucket=bucket_name,
                                        CreateBucketConfiguration=location)
        except ClientError as e:
            logging.error(e)
            return False
        return True


    def upload_file(self,file_name, bucket, object_name=None):
        """Upload a file to an S3 bucket

        :param file_name: File to upload
        :param bucket: Bucket to upload to
        :param object_name: S3 object name. If not specified then file_name is used
        :return: True if file was uploaded, else False
        """

        # If S3 object_name was not specified, use file_name
        if object_name is None:
            object_name = os.path.basename(file_name)

        # Upload the file
        #s3_client = boto3.client('s3')
        try:
            response = self.s3_client.upload_file(file_name, bucket, object_name)
        except ClientError as e:
            logging.error(e)
            print(f"{file_name} not found in s3 {bucket}.")
            raise e
    

    def download_file(self, bucket, file_name, directory):

        try:

            self.s3_client.download_file(bucket,file_name, directory)

        except ClientError as e:
            print(f"{file_name} not found in s3 {bucket}.")
            raise e
        except Exception as e:
            raise e