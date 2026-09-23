"""Explicit bucket administration, never called by the API entrypoint."""

import os

from minio import Minio
from minio.commonconfig import ENABLED, Filter
from minio.error import S3Error
from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule


def main():
    client = Minio(
        os.environ["MINIO_ENDPOINT"],
        access_key=os.environ["MINIO_ACCESS_KEY"],
        secret_key=os.environ["MINIO_SECRET_KEY"],
        secure=os.environ.get("MINIO_SECURE", "false") == "true",
    )
    bucket = os.environ["MINIO_BUCKET"]
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    try:
        policy = client.get_bucket_policy(bucket)
    except S3Error as exc:
        if exc.code != "NoSuchBucketPolicy":
            raise
    else:
        if policy:
            raise RuntimeError("Existing bucket policy needs explicit security review")
    client.set_bucket_lifecycle(
        bucket,
        LifecycleConfig(
            [
                Rule(
                    ENABLED,
                    rule_filter=Filter(prefix=prefix),
                    rule_id=name,
                    expiration=Expiration(days=int(os.environ.get(key, default))),
                )
                for prefix, name, key, default in [
                    ("original/", "expire-original", "ORIGINAL_RETENTION_DAYS", "30"),
                    (
                        "annotated/",
                        "expire-annotated",
                        "ANNOTATED_RETENTION_DAYS",
                        "90",
                    ),
                ]
            ]
        ),
    )
    print("Private bucket checked; lifecycle applied. IAM provisioning is separate.")


if __name__ == "__main__":
    main()
