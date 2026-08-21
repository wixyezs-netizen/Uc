import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _parse_admin_ids(raw: str) -> list[int]:
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


@dataclass
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: list[int] = field(default_factory=lambda: _parse_admin_ids(os.getenv("ADMIN_IDS", "")))

    # ЮMoney (yoomoney.ru) — приём платежей через quickpay-форму + проверка через API истории операций
    yoomoney_wallet: str = os.getenv("YOOMONEY_WALLET", "")
    yoomoney_token: str = os.getenv("YOOMONEY_TOKEN", "")

    referral_percent: float = float(os.getenv("REFERRAL_PERCENT", "5"))  # % от суммы заказа рефереру
    db_path: str = os.getenv("DB_PATH", "sqlite+aiosqlite:///uc_shop.db")

    payment_check_interval: int = int(os.getenv("PAYMENT_CHECK_INTERVAL", "20"))  # сек, фоновая проверка оплат
    support_username: str = os.getenv("SUPPORT_USERNAME", "support")


config = Config()
