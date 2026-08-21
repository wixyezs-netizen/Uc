from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import database as db
from bot import keyboards as kb
from bot.config import config
from bot.states import AddProductStates

router = Router(name="admin")


def is_admin(user_id: int) -> bool:
    return user_id in config.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 Админ-панель", reply_markup=kb.admin_menu())


@router.callback_query(F.data == "adm_menu")
async def cb_adm_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await state.clear()
    await call.message.edit_text("🛠 Админ-панель", reply_markup=kb.admin_menu())
    await call.answer()


# ---------- СТАТИСТИКА ----------

@router.callback_query(F.data == "adm_stats")
async def cb_adm_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    async with db.async_session() as session:
        stats = await db.get_stats(session)
    await call.message.edit_text(
        "📊 <b>Статистика</b>\n\n"
        f"Пользователей: {stats['users']}\n"
        f"Всего заказов: {stats['orders']}\n"
        f"Оплаченных заказов: {stats['paid_orders']}\n"
        f"В обработке (не оплачены): {stats['pending_orders']}\n"
        f"Выручка: {stats['revenue']:.0f}₽",
        reply_markup=kb.admin_menu(),
    )
    await call.answer()


# ---------- ЗАКАЗЫ ----------

@router.callback_query(F.data == "adm_orders")
async def cb_adm_orders(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    async with db.async_session() as session:
        orders = await db.get_paid_orders(session)
    if not orders:
        await call.message.edit_text("Нет заказов, ожидающих выдачи UC.", reply_markup=kb.admin_menu())
        await call.answer()
        return
    await call.message.edit_text(
        "🧾 Оплаченные заказы, ожидающие начисления UC:",
        reply_markup=kb.admin_orders_kb(orders),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_order_"))
async def cb_adm_order_detail(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    order_id = int(call.data.split("_")[2])
    async with db.async_session() as session:
        order = await db.get_order(session, order_id)
    if not order:
        await call.answer("Заказ не найден", show_alert=True)
        return
    await call.message.edit_text(
        f"Заказ #{order.id}\n"
        f"Товар: {order.product.name}\n"
        f"Player ID: <code>{order.game_id}</code>\n"
        f"Сумма: {order.amount:.0f}₽\n"
        f"Покупатель: @{order.user.username or order.user.tg_id}\n"
        f"Статус: {order.status}",
        reply_markup=kb.admin_order_detail_kb(order.id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_complete_"))
async def cb_adm_complete(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return await call.answer()
    order_id = int(call.data.split("_")[2])
    async with db.async_session() as session:
        order = await db.get_order(session, order_id)
        if not order:
            await call.answer("Заказ не найден", show_alert=True)
            return
        await db.mark_order_completed(session, order)
        buyer_tg_id = order.user.tg_id
        product_name = order.product.name

    try:
        await bot.send_message(buyer_tg_id, f"✅ UC по заказу «{product_name}» зачислены на ваш аккаунт. Приятной игры!")
    except Exception:
        pass

    await call.answer("Заказ отмечен выполненным ✅")
    await cb_adm_orders(call)


@router.callback_query(F.data.startswith("adm_cancel_"))
async def cb_adm_cancel(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        return await call.answer()
    order_id = int(call.data.split("_")[2])
    async with db.async_session() as session:
        order = await db.get_order(session, order_id)
        if not order:
            await call.answer("Заказ не найден", show_alert=True)
            return
        await db.mark_order_cancelled(session, order)
        buyer_tg_id = order.user.tg_id

    try:
        await bot.send_message(buyer_tg_id, f"❌ Заказ #{order.id} был отменён администратором. "
                                             f"Если оплата прошла — обратитесь в поддержку.")
    except Exception:
        pass

    await call.answer("Заказ отменён")
    await cb_adm_orders(call)


# ---------- ТОВАРЫ ----------

@router.callback_query(F.data == "adm_products")
async def cb_adm_products(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    async with db.async_session() as session:
        products = await db.get_all_products(session)
    await call.message.edit_text("📦 Товары:", reply_markup=kb.admin_products_kb(products))
    await call.answer()


@router.callback_query(F.data.startswith("adm_product_"))
async def cb_adm_product_detail(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    product_id = int(call.data.split("_")[2])
    async with db.async_session() as session:
        product = await db.get_product(session, product_id)
    if not product:
        await call.answer("Товар не найден", show_alert=True)
        return
    status = "включён 🟢" if product.is_active else "выключен 🔴"
    await call.message.edit_text(
        f"{product.name}\nUC: {product.amount_uc}\nЦена: {product.price:.0f}₽\nСтатус: {status}",
        reply_markup=kb.admin_product_detail_kb(product.id),
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm_toggle_"))
async def cb_adm_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    product_id = int(call.data.split("_")[2])
    async with db.async_session() as session:
        await db.toggle_product(session, product_id)
    await call.answer("Статус изменён")
    await cb_adm_products(call)


@router.callback_query(F.data.startswith("adm_delete_"))
async def cb_adm_delete(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer()
    product_id = int(call.data.split("_")[2])
    async with db.async_session() as session:
        await db.delete_product(session, product_id)
    await call.answer("Товар удалён")
    await cb_adm_products(call)


@router.callback_query(F.data == "adm_add_product")
async def cb_adm_add_product(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()
    await state.set_state(AddProductStates.waiting_name)
    await call.message.edit_text("Введите название товара (например: «325 UC»):", reply_markup=kb.cancel_fsm_kb())
    await call.answer()


@router.message(AddProductStates.waiting_name)
async def adm_product_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProductStates.waiting_amount)
    await message.answer("Введите количество UC (число):")


@router.message(AddProductStates.waiting_amount)
async def adm_product_amount(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("Нужно целое число. Введите количество UC:")
        return
    await state.update_data(amount_uc=int(message.text.strip()))
    await state.set_state(AddProductStates.waiting_price)
    await message.answer("Введите цену в рублях (число):")


@router.message(AddProductStates.waiting_price)
async def adm_product_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("Нужно число. Введите цену в рублях:")
        return

    data = await state.get_data()
    async with db.async_session() as session:
        await db.add_product(session, name=data["name"], amount_uc=data["amount_uc"], price=price)
    await state.clear()
    await message.answer(f"✅ Товар «{data['name']}» добавлен.", reply_markup=kb.admin_menu())
