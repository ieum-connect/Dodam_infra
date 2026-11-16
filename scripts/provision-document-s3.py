"""Run in authenticated AWS CloudShell. Only provisions Dodam's private document storage."""
import json
import boto3

REGION = "ap-southeast-2"
ACCOUNT = "515517431993"
INSTANCE = "i-004fffff12bc8ecfb"
BUCKET = f"dodam-documents-{ACCOUNT}-{REGION}"
ROLE = "dodam-ec2-document-storage"

def main():
    assert boto3.client("sts").get_caller_identity()["Account"] == ACCOUNT
    s3 = boto3.client("s3", region_name=REGION)
    ec2 = boto3.client("ec2", region_name=REGION)
    iam = boto3.client("iam")
    instance = ec2.describe_instances(InstanceIds=[INSTANCE])["Reservations"][0]["Instances"][0]
    if instance.get("IamInstanceProfile"):
        raise RuntimeError("Instance already has a role; review it instead of replacing it")
    s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION},
                     ObjectOwnership="BucketOwnerEnforced")
    s3.put_public_access_block(Bucket=BUCKET, PublicAccessBlockConfiguration={
        "BlockPublicAcls": True, "IgnorePublicAcls": True,
        "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_encryption(Bucket=BUCKET, ServerSideEncryptionConfiguration={"Rules": [
        {"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
    s3.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"})
    s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps({"Version": "2012-10-17", "Statement": [{
        "Effect": "Deny", "Principal": "*", "Action": "s3:*",
        "Resource": [f"arn:aws:s3:::{BUCKET}", f"arn:aws:s3:::{BUCKET}/*"],
        "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}))
    s3.put_bucket_cors(Bucket=BUCKET, CORSConfiguration={"CORSRules": [{
        "AllowedOrigins": ["https://dodam-ieum.duckdns.org"],
        "AllowedMethods": ["GET", "HEAD"], "AllowedHeaders": ["*"], "MaxAgeSeconds": 300}]})
    iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps({
        "Version": "2012-10-17", "Statement": [{"Effect": "Allow",
        "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]}))
    iam.put_role_policy(RoleName=ROLE, PolicyName="DodamDocumentObjects", PolicyDocument=json.dumps({
        "Version": "2012-10-17", "Statement": [
            {"Effect": "Allow", "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
             "Resource": f"arn:aws:s3:::{BUCKET}"},
            {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
             "Resource": f"arn:aws:s3:::{BUCKET}/*"}]}))
    iam.create_instance_profile(InstanceProfileName=ROLE)
    iam.add_role_to_instance_profile(InstanceProfileName=ROLE, RoleName=ROLE)
    print(json.dumps({"bucket": BUCKET, "role": ROLE, "instance": INSTANCE,
        "next": "After IAM propagation, associate this instance profile with the instance"}))

if __name__ == "__main__":
    main()
