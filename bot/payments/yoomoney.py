"""
Приём платежей через ЮMoney (yoomoney.ru).

1) generate_payment_link — формирует ссылку на quickpay-форму ЮMoney, где
   пользователь оплачивает картой РФ / с баланса кошелька / через СБП.
2) check_payment — обращается к API истории операций ЮMoney (нужен access_token
   с правом history) и ищет входящую операцию с нужным label и суммой.

Как получить YOOMONEY_TOKEN:
   https://yoomoney.ru/docs/wallet/using-api/authorization/basics
   Приложению нужно право доступа "Просмотр истории операций" (operation-history).

Если вместо ЮMoney нужен QIWI — структура аналогичная: свой modul с
generate_payment_link()/check_payment(), который подключается в handlers/user.py
вместо этого файла.
"""

import aiohttp

from bot.config import config

YOOMONEY_HISTORY_URL = "https://yoomoney.ru/api/operation-history"


def generate_payment_link(amount: float, label: str) -> str:
    return (
        "https://yoomoney.ru/quickpay/confirm.xml"
        f"?receiver={config.yoomoney_wallet}"
        "&quickpay-form=shop"
        f"&targets=Order%20{label}"
        "&paymentType=AC"
        f"&sum={amount:.2f}"
        f"&label={label}"
    )


async def check_payment(label: str, expected_amount: float) -> bool:
    """Возвращает True, если найдена входящая оплата по этому label на нужную сумму (с учётом комиссии)."""
    if not config.yoomoney_token:
        return False

    headers = {"Authorization": f"Bearer {config.yoomoney_token}"}
    data = {"label": label, "records": 5}

    async with aiohttp.ClientSession() as session:
        async with session.post(YOOMONEY_HISTORY_URL, headers=headers, data=data) as resp:
            if resp.status != 200:
                return False
            payload = await resp.json()

    for operation in payload.get("operations", []):
        if operation.get("direction") != "in":
            continue
        if operation.get("label") != label:
            continue
        if operation.get("status") != "success":
            continue
        amount = float(operation.get("amount", 0))
        # у плательщика может списаться чуть больше из-за комиссии сервиса,
        # поэтому сверяем, что зачислено не меньше ожидаемой суммы (с небольшим допуском)
        if amount + 0.01 >= expected_amount * 0.97:
            return True

    return False
