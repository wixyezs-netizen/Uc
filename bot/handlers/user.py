from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import database as db
from bot import keyboards as kb
from bot.config import config
from bot.payments import yoomoney
from bot.states import BuyStates

router = Router(name="user")


def _ref_id_from_args(text: str) -> int | None:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    arg = parts[1].strip()
    if arg.startswith("ref_") and arg[4:].isdigit():
        return int(arg[4:])
    return None


@router.message(CommandStart())
async def cmd_start(message: Message):
    referrer_tg_id = _ref_id_from_args(message.text or "")
    async with db.async_session() as session:
        await db.get_or_create_user(
            session,
            tg_id=message.from_user.id,
            username=message.from_user.username,
            referrer_tg_id=referrer_tg_id,
        )
    await message.answer(
        "👋 Добро пожаловать в <b>UC Shop</b>!\n\n"
        "Здесь можно быстро и выгодно купить UC (Unknown Cash) для PUBG Mobile.\n"
        "Оплата картой РФ / ЮMoney. Зачисление на аккаунт — вручную после проверки оплаты, обычно в течение нескольких минут.",
        reply_markup=kb.main_menu(),
    )


@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Главное меню:", reply_markup=kb.main_menu())
    await call.answer()


@router.callback_query(F.data == "support")
async def cb_support(call: CallbackQuery):
    await call.message.edit_text(
        f"По всем вопросам пишите: @{config.support_username}",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()


# ---------- КАТАЛОГ ----------

@router.callback_query(F.data == "catalog")
async def cb_catalog(call: CallbackQuery):
    async with db.async_session() as session:
        products = await db.get_active_products(session)
    if not products:
        await call.message.edit_text("Каталог временно пуст 😔", reply_markup=kb.back_to_menu())
        await call.answer()
        return
    await call.message.edit_text("Выберите пакет UC:", reply_markup=kb.catalog_kb(products))
    await call.answer()


@router.callback_query(F.data.startswith("product_"))
async def cb_product(call: CallbackQuery):
    product_id = int(call.data.split("_")[1])
    async with db.async_session() as session:
        product = await db.get_product(session, product_id)
    if not product or not product.is_active:
        await call.answer("Товар недоступен", show_alert=True)
        return
    await call.message.edit_text(
        f"<b>{product.name}</b>\nЦена: {product.price:.0f}₽\n\nПодтвердите покупку:",
        reply_markup=kb.product_confirm_kb(product.id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("buy_"))
async def cb_buy(call: CallbackQuery, state: FSMContext):
    product_id = int(call.data.split("_")[1])
    async with db.async_session() as session:
        product = await db.get_product(session, product_id)
    if not product or not product.is_active:
        await call.answer("Товар недоступен", show_alert=True)
        return
    await state.update_data(product_id=product_id)
    await state.set_state(BuyStates.waiting_game_id)
    await call.message.edit_text(
        "Введите ваш <b>Player ID (UID)</b> из игры, куда нужно зачислить UC:\n\n"
        "<i>Найти ID можно в профиле игрока в PUBG Mobile, под ником.</i>"
    )
    await call.answer()


@router.message(BuyStates.waiting_game_id)
async def process_game_id(message: Message, bot: Bot, state: FSMContext):
    game_id = (message.text or "").strip()
    if not game_id or not game_id.isdigit() or len(game_id) < 5:
        await message.answer("Похоже, ID некорректный. Введите числовой Player ID из игры:")
        return

    data = await state.get_data()
    product_id = data["product_id"]
    await state.clear()

    async with db.async_session() as session:
        product = await db.get_product(session, product_id)
        if not product or not product.is_active:
            await message.answer("Товар больше недоступен.", reply_markup=kb.main_menu())
            return

        user = await db.get_or_create_user(session, tg_id=message.from_user.id, username=message.from_user.username)
        order = await db.create_order(session, user_id=user.id, product_id=product.id,
                                       game_id=game_id, amount=product.price)

    pay_url = yoomoney.generate_payment_link(order.amount, order.label)
    await message.answer(
        f"🧾 Заказ #{order.id}\n"
        f"Товар: {product.name}\n"
        f"Player ID: {game_id}\n"
        f"Сумма к оплате: <b>{order.amount:.0f}₽</b>\n\n"
        "Нажмите «Оплатить», а после оплаты — «Я оплатил / проверить».",
        reply_markup=kb.payment_kb(order.id, pay_url),
    )


@router.callback_query(F.data.startswith("check_"))
async def cb_check_payment(call: CallbackQuery, bot: Bot):
    order_id = int(call.data.split("_")[1])
    async with db.async_session() as session:
        order = await db.get_order(session, order_id)
        if not order:
            await call.answer("Заказ не найден", show_alert=True)
            return
        if order.status != "pending":
            await call.answer(f"Статус заказа: {order.status}", show_alert=True)
            return

        paid = await yoomoney.check_payment(order.label, order.amount)
        if not paid:
            await call.answer("Оплата пока не найдена. Попробуйте через минуту.", show_alert=True)
            return

        await db.mark_order_paid(session, order)
        ref_result = await db.credit_referral_bonus(session, order)

    await call.message.edit_text(
        f"✅ Оплата заказа #{order.id} подтверждена!\n"
        "UC будут зачислены на ваш аккаунт в ближайшее время. Спасибо за покупку!",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer("Оплата найдена ✅")

    for admin_id in config.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"💰 Новый оплаченный заказ #{order.id}\n"
                f"Товар: {order.product.name}\n"
                f"Player ID: {order.game_id}\n"
                f"Сумма: {order.amount:.0f}₽\n"
                f"Покупатель: @{order.user.username or order.user.tg_id}",
            )
        except Exception:
            pass

    if ref_result:
        referrer, bonus = ref_result
        try:
            await bot.send_message(
                referrer.tg_id,
                f"🤝 Ваш реферал совершил покупку! Начислено {bonus:.2f}₽ реферального бонуса.\n"
                f"Баланс бонусов: {referrer.balance:.2f}₽",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("cancel_"))
async def cb_cancel_order(call: CallbackQuery):
    order_id = int(call.data.split("_")[1])
    async with db.async_session() as session:
        order = await db.get_order(session, order_id)
        if not order or order.status != "pending":
            await call.answer("Заказ нельзя отменить", show_alert=True)
            return
        await db.mark_order_cancelled(session, order)
    await call.message.edit_text("Заказ отменён.", reply_markup=kb.main_menu())
    await call.answer()


# ---------- ПРОФИЛЬ / РЕФЕРАЛКА ----------

@router.callback_query(F.data == "profile")
async def cb_profile(call: CallbackQuery):
    async with db.async_session() as session:
        user = await db.get_or_create_user(session, tg_id=call.from_user.id, username=call.from_user.username)
        refs_count = await db.count_referrals(session, user.id)
    await call.message.edit_text(
        f"👤 <b>Профиль</b>\n\n"
        f"ID: <code>{user.tg_id}</code>\n"
        f"Реферальный бонус: {user.balance:.2f}₽\n"
        f"Всего заработано с рефералов: {user.ref_earned_total:.2f}₽\n"
        f"Приглашено рефералов: {refs_count}",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()


@router.callback_query(F.data == "referral")
async def cb_referral(call: CallbackQuery, bot: Bot):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{call.from_user.id}"
    await call.message.edit_text(
        "🤝 <b>Реферальная система</b>\n\n"
        f"Приглашайте друзей и получайте {config.referral_percent:.0f}% с каждой их покупки бонусами на баланс.\n\n"
        f"Ваша ссылка:\n<code>{link}</code>",
        reply_markup=kb.back_to_menu(),
    )
    await call.answer()
