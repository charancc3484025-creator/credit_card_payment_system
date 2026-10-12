import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _get_fernet() -> Fernet:
    if not settings.CARD_ENCRYPTION_KEY:
        raise RuntimeError("CARD_ENCRYPTION_KEY is missing in .env")
    return Fernet(settings.CARD_ENCRYPTION_KEY.encode())


def encrypt_card_number(card_number: str) -> str:
    return _get_fernet().encrypt(card_number.encode()).decode()


def decrypt_card_number(encrypted_value: str) -> str:
    try:
        return _get_fernet().decrypt(encrypted_value.encode()).decode()
    except InvalidToken:
        raise ValueError("Unable to decrypt card number - check CARD_ENCRYPTION_KEY")


def card_fingerprint(card_number: str) -> str:
    key = settings.CARD_ENCRYPTION_KEY.encode()
    return hmac.new(key, card_number.encode(), hashlib.sha256).hexdigest()


def mask_card_number(last_four: str) -> str:
    return f"**** **** **** {last_four}"
