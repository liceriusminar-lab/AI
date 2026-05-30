"""
encryption.py — шифрование истории чатов Сильфиетты
Использует Fernet (AES-128 + HMAC) из библиотеки cryptography
"""
import os
import json
import base64
from pathlib import Path

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

KEY_FILE      = Path.home() / ".ai-assistant" / ".key"
SALT_FILE     = Path.home() / ".ai-assistant" / ".salt"
ENCRYPTED_DIR = Path.home() / ".ai-assistant" / "encrypted"


def _get_or_create_key() -> bytes:
    """Генерирует или загружает ключ шифрования."""
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    KEY_FILE.chmod(0o600)  # только владелец
    return key


def _get_fernet() -> "Fernet":
    key = _get_or_create_key()
    return Fernet(key)


def encrypt_data(data: str) -> bytes:
    """Шифрует строку и возвращает байты."""
    if not HAS_CRYPTO:
        return data.encode("utf-8")
    f = _get_fernet()
    return f.encrypt(data.encode("utf-8"))


def decrypt_data(data: bytes) -> str:
    """Расшифровывает байты и возвращает строку."""
    if not HAS_CRYPTO:
        return data.decode("utf-8")
    f = _get_fernet()
    return f.decrypt(data).decode("utf-8")


def is_encryption_available() -> bool:
    return HAS_CRYPTO


def get_encryption_status() -> str:
    if not HAS_CRYPTO:
        return "❌ Недоступно (нет cryptography)"
    if KEY_FILE.exists():
        return "🔐 Включено"
    return "🔓 Выключено"


def encrypt_file(src_path: Path, dst_path: Path):
    """Шифрует файл."""
    data = src_path.read_text(encoding="utf-8")
    encrypted = encrypt_data(data)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(encrypted)


def decrypt_file(src_path: Path) -> str:
    """Расшифровывает файл и возвращает содержимое."""
    data = src_path.read_bytes()
    return decrypt_data(data)


def rotate_key():
    """Перегенерирует ключ (старые данные станут недоступны!)."""
    if KEY_FILE.exists():
        KEY_FILE.unlink()
    _get_or_create_key()
