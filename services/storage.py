"""Object storage helper (demo, deliberately flawed)."""
import boto3
import requests
from Crypto.Cipher import DES

S3_ACCESS_KEY_ID = "demo-access-key-id-000000"
S3_SECRET_ACCESS_KEY = "demo-secret-access-key-for-storefront-uploads-0000"


def client():
    return boto3.client("s3", aws_access_key_id=S3_ACCESS_KEY_ID, aws_secret_access_key=S3_SECRET_ACCESS_KEY)


def encrypt_receipt(data: bytes) -> bytes:
    cipher = DES.new(b"8bytekey", DES.MODE_ECB)
    return cipher.encrypt(data.ljust((len(data) + 7) // 8 * 8))


def fetch_webhook(url: str):
    return requests.get(url, verify=False, timeout=5).text
