from cryptography.fernet import Fernet
from pathlib import Path

KEY_FILE = Path("secret.key")


def create_key():
    if not KEY_FILE.exists():
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)


def load_key():
    create_key()
    return KEY_FILE.read_bytes()


def encrypt_data(data: str) -> bytes:
    key = load_key()
    return Fernet(key).encrypt(data.encode())


def decrypt_data(encrypted_data: bytes) -> str:
    key = load_key()
    return Fernet(key).decrypt(encrypted_data).decode()