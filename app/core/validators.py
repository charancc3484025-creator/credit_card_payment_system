import re
from datetime import date

COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "qwerty123",
    "iloveyou", "admin123", "welcome1", "letmein1", "Password@123", "Admin@123",
}


def validate_password_strength(password: str, email: str = "") -> list[str]:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit.")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Password must contain at least one special character.")
    if password in COMMON_PASSWORDS or password.lower() in COMMON_PASSWORDS:
        errors.append("This password is too common.")
    if email and email.split("@")[0].lower() in password.lower():
        errors.append("Password is too similar to the email.")
    return errors


def clean_card_number(card_number: str) -> str:
    return re.sub(r"[\s-]", "", card_number or "")


def luhn_check(card_number: str) -> bool:
    if not card_number.isdigit():
        return False
    total = 0
    for index, ch in enumerate(card_number[::-1]):
        digit = int(ch)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def detect_card_brand(card_number: str) -> str:
    if re.match(r"^4\d{12}(\d{3})?(\d{3})?$", card_number):
        return "VISA"
    if re.match(r"^(5[1-5]\d{14}|2(2[2-9][1-9]|2[3-9]\d|[3-6]\d{2}|7[01]\d|720)\d{12})$", card_number):
        return "MASTERCARD"
    if re.match(r"^3[47]\d{13}$", card_number):
        return "AMEX"
    if re.match(r"^(60|65|81|82|508)\d{11,14}$", card_number):
        return "RUPAY"
    if re.match(r"^6(011|5\d{2})\d{12}$", card_number):
        return "DISCOVER"
    return "UNKNOWN"


def validate_card_number(card_number: str) -> str:
    number = clean_card_number(card_number)
    if not number.isdigit():
        raise ValueError("Card number must contain only digits.")
    if len(number) < 13 or len(number) > 19:
        raise ValueError("Card number must be between 13 and 19 digits.")
    if not luhn_check(number):
        raise ValueError("Invalid card number.")
    if detect_card_brand(number) == "UNKNOWN":
        raise ValueError("Card type is not supported.")
    return number


def validate_expiry(month: int, year: int) -> None:
    if month < 1 or month > 12:
        raise ValueError("Expiry month must be between 1 and 12.")
    today = date.today()
    if year < today.year or (year == today.year and month < today.month):
        raise ValueError("Card has expired.")
    if year > today.year + 20:
        raise ValueError("Expiry year is not valid.")


def validate_cvv(cvv: str, card_brand: str) -> None:
    expected_length = 4 if card_brand == "AMEX" else 3
    if not cvv or not cvv.isdigit() or len(cvv) != expected_length:
        raise ValueError(f"CVV must be {expected_length} digits.")


def validate_phone_number(phone: str) -> str:
    if phone and not re.match(r"^\+?\d{10,15}$", phone):
        raise ValueError("Enter a valid phone number (10 to 15 digits).")
    return phone
