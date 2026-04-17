from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, Text, ForeignKey, Enum
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
import enum

Base = declarative_base()

class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TransactionType(str, enum.Enum):
    DEPOSIT = "deposit"
    PURCHASE = "purchase"
    REFUND = "refund"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(50), unique=True, nullable=False)
    username = Column(String(100))
    full_name = Column(String(200))
    balance = Column(Float, default=0.0)
    total_spent = Column(Float, default=0.0)
    is_banned = Column(Boolean, default=False)
    referral_code = Column(String(20), unique=True)
    referred_by = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

    orders = relationship("Order", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    emoji = Column(String(10), default="📦")
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    category = relationship("Category", back_populates="products")
    codes = relationship("Code", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")

class Code(Base):
    __tablename__ = "codes"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    code_value = Column(Text, nullable=False)
    is_sold = Column(Boolean, default=False)
    sold_at = Column(DateTime, nullable=True)
    order_item_id = Column(Integer, nullable=True)

    product = relationship("Product", back_populates="codes")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    order_code = Column(String(20), unique=True)
    total_amount = Column(Float, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.COMPLETED)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer, default=1)
    unit_price = Column(Float)
    codes_delivered = Column(Text)  # JSON list of codes

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(Enum(TransactionType))
    amount = Column(Float)
    balance_before = Column(Float)
    balance_after = Column(Float)
    description = Column(String(500))
    reference = Column(String(100))  # order_code or deposit ref
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_by = Column(String(100), nullable=True)

    user = relationship("User", back_populates="transactions")

class DepositRequest(Base):
    __tablename__ = "deposit_requests"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    telegram_id = Column(String(50))
    amount = Column(Float)
    transfer_code = Column(String(50), unique=True)
    status = Column(String(20), default="pending")  # pending, confirmed, rejected
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by = Column(String(100), nullable=True)

    user = relationship("User")

class BotSettings(Base):
    __tablename__ = "bot_settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)


# Database setup
def get_engine(db_url):
    return create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})

def init_db(engine):
    Base.metadata.create_all(engine)

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()

def seed_data(session):
    """Insert default data"""
    # Categories
    cats = [
        Category(name="Facebook", emoji="👤", description="Tài khoản Facebook các loại", sort_order=1),
        Category(name="Zalo", emoji="💬", description="Tài khoản Zalo", sort_order=2),
        Category(name="Gmail", emoji="📧", description="Tài khoản Google Gmail", sort_order=3),
        Category(name="TikTok", emoji="🎵", description="Tài khoản TikTok", sort_order=4),
        Category(name="Instagram", emoji="📸", description="Tài khoản Instagram", sort_order=5),
    ]
    for cat in cats:
        existing = session.query(Category).filter_by(name=cat.name).first()
        if not existing:
            session.add(cat)
    session.commit()

    # Sample products
    fb = session.query(Category).filter_by(name="Facebook").first()
    zalo = session.query(Category).filter_by(name="Zalo").first()
    gmail = session.query(Category).filter_by(name="Gmail").first()

    sample_products = [
        Product(category_id=fb.id, name="Facebook Via Cổ 2010-2015", description="Via cổ, đã verify phone, uy tín", price=15000, stock=0),
        Product(category_id=fb.id, name="Facebook Via Trắng 1-3 Tháng", description="Tài khoản mới tạo, email verify", price=5000, stock=0),
        Product(category_id=fb.id, name="Facebook BM1 Limit 250$", description="Business Manager 1 tài khoản ads, limit 250$", price=50000, stock=0),
        Product(category_id=zalo.id, name="Zalo Số Thật Việt Nam", description="SĐT Việt Nam, đã verify, full info", price=8000, stock=0),
        Product(category_id=gmail.id, name="Gmail Cổ 2015-2018", description="Gmail cổ, recovery email, phone verify", price=10000, stock=0),
        Product(category_id=gmail.id, name="Gmail Mới Bulk (Batch 10)", description="10 gmail mới tạo, chưa qua sử dụng", price=30000, stock=0),
    ]
    for p in sample_products:
        existing = session.query(Product).filter_by(name=p.name).first()
        if not existing:
            session.add(p)
    session.commit()

    # Default settings
    defaults = {
        "welcome_message": "👋 Chào mừng bạn đến với Shop Mã Xã Hội!\n\n🔥 Chúng tôi cung cấp tài khoản Facebook, Zalo, Gmail, TikTok chất lượng cao với giá tốt nhất thị trường.\n\n💯 Cam kết: Hàng chất lượng | Giao ngay | Hỗ trợ 24/7",
        "maintenance_mode": "false",
        "maintenance_message": "🔧 Bot đang bảo trì, vui lòng quay lại sau!",
        "min_deposit": "10000",
        "bonus_rate": "0",
    }
    for k, v in defaults.items():
        existing = session.query(BotSettings).filter_by(key=k).first()
        if not existing:
            session.add(BotSettings(key=k, value=v))
    session.commit()
