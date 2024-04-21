import logging
import boto3
from botocore.exceptions import ClientError



def get_aws_bucket(bucket_name):
    """
    Create an AWS client using the AWS credentials.
    
    Returns:
        client: The AWS client object.
    """
    # Create a session using your AWS credentials
    session = boto3.Session(
        aws_access_key_id='AKIA2G5UZXNS2WFIG4XH',
        aws_secret_access_key='HHn/Mdx9a7xSGZYZ758GEisLCCXi7+o8W0lhZaIU',
        region_name='us-east-2'
    )

    # Create an S3 resource object using the session
    s3 = session.resource('s3')

    # Access the bucket
    bucket = s3.Bucket(bucket_name)

    return bucket
