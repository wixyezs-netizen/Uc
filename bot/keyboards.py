from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database import Product, Order


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Каталог UC", callback_data="catalog")
    kb.button(text="👤 Профиль", callback_data="profile")
    kb.button(text="🤝 Реферальная система", callback_data="referral")
    kb.button(text="🆘 Поддержка", callback_data="support")
    kb.adjust(1)
    return kb.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="menu")
    return kb.as_markup()


def catalog_kb(products: list[Product]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in products:
        kb.button(text=f"{p.name} — {p.price:.0f}₽", callback_data=f"product_{p.id}")
    kb.button(text="⬅️ В меню", callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def product_confirm_kb(product_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Купить", callback_data=f"buy_{product_id}")
    kb.button(text="⬅️ К каталогу", callback_data="catalog")
    kb.adjust(1)
    return kb.as_markup()


def payment_kb(order_id: int, pay_url: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Оплатить", url=pay_url)
    kb.button(text="🔄 Я оплатил / проверить", callback_data=f"check_{order_id}")
    kb.button(text="❌ Отменить заказ", callback_data=f"cancel_{order_id}")
    kb.adjust(1)
    return kb.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="adm_stats")
    kb.button(text="🧾 Заказы в обработке", callback_data="adm_orders")
    kb.button(text="📦 Товары", callback_data="adm_products")
    kb.adjust(1)
    return kb.as_markup()


def admin_orders_kb(orders: list[Order]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for o in orders:
        kb.button(text=f"#{o.id} · {o.product.name} · {o.amount:.0f}₽", callback_data=f"adm_order_{o.id}")
    kb.button(text="⬅️ Админ-меню", callback_data="adm_menu")
    kb.adjust(1)
    return kb.as_markup()


def admin_order_detail_kb(order_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Выполнен (UC начислены)", callback_data=f"adm_complete_{order_id}")
    kb.button(text="❌ Отменить заказ", callback_data=f"adm_cancel_{order_id}")
    kb.button(text="⬅️ К заказам", callback_data="adm_orders")
    kb.adjust(1)
    return kb.as_markup()


def admin_products_kb(products: list[Product]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in products:
        status = "🟢" if p.is_active else "🔴"
        kb.button(text=f"{status} {p.name} — {p.price:.0f}₽", callback_data=f"adm_product_{p.id}")
    kb.button(text="➕ Добавить товар", callback_data="adm_add_product")
    kb.button(text="⬅️ Админ-меню", callback_data="adm_menu")
    kb.adjust(1)
    return kb.as_markup()


def admin_product_detail_kb(product_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Вкл/выкл", callback_data=f"adm_toggle_{product_id}")
    kb.button(text="🗑 Удалить", callback_data=f"adm_delete_{product_id}")
    kb.button(text="⬅️ К товарам", callback_data="adm_products")
    kb.adjust(1)
    return kb.as_markup()


def cancel_fsm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="adm_products")
    return kb.as_markup()
