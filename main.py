import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot import database as db
from bot.config import config
from bot.handlers import admin, user
from bot.payments import yoomoney

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uc_shop_bot")


async def payment_watcher(bot: Bot):
    """Фоновая задача: раз в N секунд проверяет незавершённые заказы и автоматически
    подтверждает их, если оплата на ЮMoney уже прошла (пользователю не нужно нажимать кнопку)."""
    while True:
        try:
            async with db.async_session() as session:
                pending = await db.get_pending_orders(session)
                for order in pending:
                    paid = await yoomoney.check_payment(order.label, order.amount)
                    if not paid:
                        continue
                    await db.mark_order_paid(session, order)
                    ref_result = await db.credit_referral_bonus(session, order)

                    try:
                        await bot.send_message(
                            order.user.tg_id,
                            f"✅ Оплата заказа #{order.id} подтверждена! UC будут зачислены в ближайшее время.",
                        )
                    except Exception:
                        pass

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
                                f"🤝 Ваш реферал совершил покупку! Начислено {bonus:.2f}₽.",
                            )
                        except Exception:
                            pass
        except Exception:
            logger.exception("Ошибка в payment_watcher")

        await asyncio.sleep(config.payment_check_interval)


async def main():
    if not config.bot_token:
        raise RuntimeError("BOT_TOKEN не задан. Заполните .env файл (см. .env.example).")

    await db.init_db()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin.router)
    dp.include_router(user.router)

    asyncio.create_task(payment_watcher(bot))

    logger.info("Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
