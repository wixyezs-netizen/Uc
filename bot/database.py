import datetime
import uuid

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String,
    select, func
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from bot.config import config


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    balance: Mapped[float] = mapped_column(Float, default=0)  # реферальный бонус, используется как скидка
    referrer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ref_earned_total: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    amount_uc: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    game_id: Mapped[str] = mapped_column(String(64))  # ID игрока, куда зачислить UC
    amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending / paid / completed / cancelled
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    paid_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(lazy="joined")
    product: Mapped["Product"] = relationship(lazy="joined")


engine = create_async_engine(config.db_path, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # если каталог пуст — добавим стартовые пакеты UC
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(Product))
        if result.scalar_one() == 0:
            defaults = [
                Product(name="60 UC", amount_uc=60, price=99),
                Product(name="325 UC", amount_uc=325, price=449),
                Product(name="660 UC", amount_uc=660, price=849),
                Product(name="1800 UC", amount_uc=1800, price=2199),
                Product(name="3850 UC", amount_uc=3850, price=4599),
                Product(name="8100 UC", amount_uc=8100, price=8999),
            ]
            session.add_all(defaults)
            await session.commit()


# ---------- USERS ----------

async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None,
                              referrer_tg_id: int | None = None) -> User:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    user = result.scalar_one_or_none()
    if user:
        if username and user.username != username:
            user.username = username
            await session.commit()
        return user

    referrer_id = None
    if referrer_tg_id and referrer_tg_id != tg_id:
        ref_result = await session.execute(select(User).where(User.tg_id == referrer_tg_id))
        referrer = ref_result.scalar_one_or_none()
        if referrer:
            referrer_id = referrer.id

    user = User(tg_id=tg_id, username=username, referrer_id=referrer_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def count_referrals(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(select(func.count()).select_from(User).where(User.referrer_id == user_id))
    return result.scalar_one()


# ---------- PRODUCTS ----------

async def get_active_products(session: AsyncSession) -> list[Product]:
    result = await session.execute(select(Product).where(Product.is_active == True).order_by(Product.price))
    return list(result.scalars().all())


async def get_all_products(session: AsyncSession) -> list[Product]:
    result = await session.execute(select(Product).order_by(Product.price))
    return list(result.scalars().all())


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)


async def add_product(session: AsyncSession, name: str, amount_uc: int, price: float) -> Product:
    product = Product(name=name, amount_uc=amount_uc, price=price)
    session.add(product)
    await session.commit()
    return product


async def toggle_product(session: AsyncSession, product_id: int) -> Product | None:
    product = await session.get(Product, product_id)
    if product:
        product.is_active = not product.is_active
        await session.commit()
    return product


async def delete_product(session: AsyncSession, product_id: int) -> bool:
    product = await session.get(Product, product_id)
    if product:
        await session.delete(product)
        await session.commit()
        return True
    return False


# ---------- ORDERS ----------

async def create_order(session: AsyncSession, user_id: int, product_id: int, game_id: str, amount: float) -> Order:
    order = Order(
        label=uuid.uuid4().hex,
        user_id=user_id,
        product_id=product_id,
        game_id=game_id,
        amount=amount,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    result = await session.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()


async def get_order_by_label(session: AsyncSession, label: str) -> Order | None:
    result = await session.execute(select(Order).where(Order.label == label))
    return result.scalar_one_or_none()


async def get_pending_orders(session: AsyncSession) -> list[Order]:
    result = await session.execute(select(Order).where(Order.status == "pending").order_by(Order.created_at))
    return list(result.scalars().all())


async def get_paid_orders(session: AsyncSession) -> list[Order]:
    result = await session.execute(select(Order).where(Order.status == "paid").order_by(Order.paid_at))
    return list(result.scalars().all())


async def mark_order_paid(session: AsyncSession, order: Order) -> None:
    order.status = "paid"
    order.paid_at = datetime.datetime.utcnow()
    await session.commit()


async def mark_order_completed(session: AsyncSession, order: Order) -> None:
    order.status = "completed"
    await session.commit()


async def mark_order_cancelled(session: AsyncSession, order: Order) -> None:
    order.status = "cancelled"
    await session.commit()


async def credit_referral_bonus(session: AsyncSession, order: Order) -> tuple[User, float] | None:
    buyer = await session.get(User, order.user_id)
    if not buyer or not buyer.referrer_id:
        return None
    referrer = await session.get(User, buyer.referrer_id)
    if not referrer:
        return None
    bonus = round(order.amount * config.referral_percent / 100, 2)
    referrer.balance += bonus
    referrer.ref_earned_total += bonus
    await session.commit()
    return referrer, bonus


# ---------- STATS ----------

async def get_stats(session: AsyncSession) -> dict:
    users_count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    orders_count = (await session.execute(select(func.count()).select_from(Order))).scalar_one()
    paid_orders_count = (await session.execute(
        select(func.count()).select_from(Order).where(Order.status.in_(["paid", "completed"]))
    )).scalar_one()
    revenue = (await session.execute(
        select(func.coalesce(func.sum(Order.amount), 0)).where(Order.status.in_(["paid", "completed"]))
    )).scalar_one()
    pending_count = (await session.execute(
        select(func.count()).select_from(Order).where(Order.status == "pending")
    )).scalar_one()
    return {
        "users": users_count,
        "orders": orders_count,
        "paid_orders": paid_orders_count,
        "pending_orders": pending_count,
        "revenue": revenue,
    }
