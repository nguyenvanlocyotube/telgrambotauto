"""
Telegram Bot - Shop Mã Xã Hội
Full-featured social accounts selling bot
"""
import asyncio
import json
import logging
import random
import string
from datetime import datetime

# ─── sửa ở đây ──────────────────────────────────────────────────
from flask import Flask
import threading

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

import config
from models import (
    get_engine, init_db, get_session, seed_data,
    User, Category, Product, Code, Order, OrderItem,
    Transaction, DepositRequest, BotSettings,
    OrderStatus, TransactionType
)

    engine = get_engine(config.DATABASE_URL)
    init_db(engine)
    print("DATABASE_URL:", config.DATABASE_URL)
    print("DB:", config.DATABASE_URL)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

engine = get_engine(config.DATABASE_URL)
init_db(engine)

def db():
    return get_session(engine)

# ─── Conversation states ───────────────────────────────────────
DEPOSIT_AMOUNT, DEPOSIT_CONFIRM = range(2)
CART_ACTION = 10
SUPPORT_MESSAGE = 20

# ─── Helpers ──────────────────────────────────────────────────
def fmt_price(amount: float) -> str:
    return f"{int(amount):,}đ"

def gen_order_code() -> str:
    return "ORD" + "".join(random.choices(string.digits, k=8))

def gen_transfer_code(telegram_id: str) -> str:
    suffix = "".join(random.choices(string.digits, k=5))
    return f"NAP{telegram_id[-4:]}{suffix}"

def gen_referral_code() -> str:
    return "REF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_or_create_user(session, update: Update) -> User:
    tg_user = update.effective_user
    user = session.query(User).filter_by(telegram_id=str(tg_user.id)).first()
    if not user:
        user = User(
            telegram_id=str(tg_user.id),
            username=tg_user.username or "",
            full_name=tg_user.full_name or "",
            referral_code=gen_referral_code()
        )
        session.add(user)
        session.commit()
    else:
        user.last_active = datetime.utcnow()
        if tg_user.username:
            user.username = tg_user.username
        session.commit()
    return user

def get_setting(session, key: str, default: str = "") -> str:
    s = session.query(BotSettings).filter_by(key=key).first()
    return s.value if s else default

def is_admin(telegram_id: int) -> bool:
    return telegram_id in config.ADMIN_IDS

def main_keyboard(is_admin_user=False):
    kb = [
        [KeyboardButton("🛍 Sản phẩm"), KeyboardButton("🛒 Giỏ hàng")],
        [KeyboardButton("📦 Đơn hàng"), KeyboardButton("💰 Nạp tiền")],
        [KeyboardButton("👤 Tài khoản"), KeyboardButton("📞 Hỗ trợ")],
    ]
    if is_admin_user:
        kb.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

# ─── /start ────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = db()
    try:
        user = get_or_create_user(session, update)

        # Check maintenance
        if get_setting(session, "maintenance_mode") == "true" and not is_admin(update.effective_user.id):
            msg = get_setting(session, "maintenance_message", "🔧 Bot đang bảo trì!")
            await update.message.reply_text(msg)
            return

        welcome = get_setting(session, "welcome_message",
            "👋 Chào mừng đến với Shop Mã Xã Hội!")

        # Handle referral
        if context.args:
            ref_code = context.args[0]
            if ref_code.startswith("REF") and not user.referred_by:
                referrer = session.query(User).filter_by(referral_code=ref_code).first()
                if referrer and referrer.telegram_id != user.telegram_id:
                    user.referred_by = ref_code
                    session.commit()

        await update.message.reply_text(
            f"{welcome}\n\n"
            f"💼 Số dư: *{fmt_price(user.balance)}*\n"
            f"👋 Xin chào, *{user.full_name or 'bạn'}*!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_keyboard(is_admin(update.effective_user.id))
        )
    finally:
        session.close()

# ─── Sản phẩm ──────────────────────────────────────────────────
async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = db()
    try:
        user = get_or_create_user(session, update)
        if get_setting(session, "maintenance_mode") == "true" and not is_admin(update.effective_user.id):
            await update.message.reply_text("🔧 Bot đang bảo trì!")
            return

        categories = session.query(Category).filter_by(is_active=True).order_by(Category.sort_order).all()
        if not categories:
            await update.message.reply_text("😔 Chưa có sản phẩm nào.")
            return

        keyboard = []
        for cat in categories:
            count = session.query(Product).filter_by(category_id=cat.id, is_active=True).count()
            # Count available stock
            total_stock = 0
            prods = session.query(Product).filter_by(category_id=cat.id, is_active=True).all()
            for p in prods:
                total_stock += p.stock
            keyboard.append([InlineKeyboardButton(
                f"{cat.emoji} {cat.name} ({total_stock} sản phẩm)",
                callback_data=f"cat_{cat.id}"
            )])

        await update.message.reply_text(
            "🛍 *Danh mục sản phẩm*\n\nChọn danh mục để xem sản phẩm:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    finally:
        session.close()

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split("_")[1])

    session = db()
    try:
        cat = session.query(Category).get(cat_id)
        products = session.query(Product).filter_by(
            category_id=cat_id, is_active=True
        ).all()

        if not products:
            await query.edit_message_text("😔 Danh mục này chưa có sản phẩm.")
            return

        keyboard = []
        for p in products:
            stock_icon = "✅" if p.stock > 0 else "❌"
            keyboard.append([InlineKeyboardButton(
                f"{stock_icon} {p.name} - {fmt_price(p.price)} ({p.stock} còn)",
                callback_data=f"prod_{p.id}"
            )])
        keyboard.append([InlineKeyboardButton("◀️ Quay lại", callback_data="back_cats")])

        await query.edit_message_text(
            f"{cat.emoji} *{cat.name}*\n{cat.description or ''}\n\n"
            f"Chọn sản phẩm để xem chi tiết:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    finally:
        session.close()

async def show_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[1])

    session = db()
    try:
        p = session.query(Product).get(prod_id)
        if not p:
            await query.edit_message_text("Sản phẩm không tồn tại.")
            return

        stock_text = f"✅ Còn hàng: {p.stock}" if p.stock > 0 else "❌ Hết hàng"
        keyboard = [
            [
                InlineKeyboardButton("➕ Thêm vào giỏ", callback_data=f"addcart_{p.id}_1"),
            ],
            [
                InlineKeyboardButton("⚡ Mua ngay 1", callback_data=f"buynow_{p.id}_1"),
                InlineKeyboardButton("⚡ Mua ngay 3", callback_data=f"buynow_{p.id}_3"),
            ],
            [InlineKeyboardButton("◀️ Quay lại", callback_data=f"cat_{p.category_id}")]
        ]

        await query.edit_message_text(
            f"📦 *{p.name}*\n\n"
            f"📝 {p.description or 'Không có mô tả'}\n\n"
            f"💰 Giá: *{fmt_price(p.price)}* / 1 tài khoản\n"
            f"📊 {stock_text}\n\n"
            f"_Chọn số lượng mua hoặc thêm vào giỏ hàng:_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    finally:
        session.close()

async def back_to_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session = db()
    try:
        categories = session.query(Category).filter_by(is_active=True).order_by(Category.sort_order).all()
        keyboard = []
        for cat in categories:
            prods = session.query(Product).filter_by(category_id=cat.id, is_active=True).all()
            total_stock = sum(p.stock for p in prods)
            keyboard.append([InlineKeyboardButton(
                f"{cat.emoji} {cat.name} ({total_stock} sản phẩm)",
                callback_data=f"cat_{cat.id}"
            )])
        await query.edit_message_text(
            "🛍 *Danh mục sản phẩm*\n\nChọn danh mục:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    finally:
        session.close()

# ─── Giỏ hàng ──────────────────────────────────────────────────
def get_cart(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "cart" not in context.user_data:
        context.user_data["cart"] = {}
    return context.user_data["cart"]

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    prod_id = int(parts[1])
    qty = int(parts[2])

    session = db()
    try:
        p = session.query(Product).get(prod_id)
        if not p or not p.is_active:
            await query.answer("Sản phẩm không tồn tại!", show_alert=True)
            return
        if p.stock <= 0:
            await query.answer("❌ Sản phẩm đã hết hàng!", show_alert=True)
            return

        cart = get_cart(context)
        key = str(prod_id)
        current = cart.get(key, {"name": p.name, "price": p.price, "qty": 0})
        current["qty"] += qty
        if current["qty"] > p.stock:
            await query.answer(f"❌ Chỉ còn {p.stock} sản phẩm!", show_alert=True)
            return
        cart[key] = current
        await query.answer(f"✅ Đã thêm {qty} '{p.name}' vào giỏ!", show_alert=True)
    finally:
        session.close()

async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cart = get_cart(context)
    if not cart:
        msg = "🛒 *Giỏ hàng trống*\n\nHãy thêm sản phẩm vào giỏ hàng!"
        if update.message:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
        return

    lines = ["🛒 *Giỏ hàng của bạn*\n"]
    total = 0
    keyboard = []
    for key, item in cart.items():
        subtotal = item["price"] * item["qty"]
        total += subtotal
        lines.append(f"• {item['name']} x{item['qty']} = *{fmt_price(subtotal)}*")
        keyboard.append([
            InlineKeyboardButton(f"➖ {item['name'][:20]}", callback_data=f"cartdec_{key}"),
            InlineKeyboardButton(f"❌ Xóa", callback_data=f"cartrem_{key}"),
        ])

    lines.append(f"\n💰 *Tổng: {fmt_price(total)}*")
    keyboard.append([InlineKeyboardButton("✅ Thanh toán", callback_data="checkout")])
    keyboard.append([InlineKeyboardButton("🗑 Xóa giỏ", callback_data="clearcart")])

    if update.message:
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    cart = get_cart(context)

    if data == "clearcart":
        context.user_data["cart"] = {}
        await query.edit_message_text("🗑 Đã xóa giỏ hàng!")
        return

    if data.startswith("cartrem_"):
        key = data.split("_", 1)[1]
        cart.pop(key, None)
    elif data.startswith("cartdec_"):
        key = data.split("_", 1)[1]
        if key in cart:
            cart[key]["qty"] -= 1
            if cart[key]["qty"] <= 0:
                cart.pop(key)

    if not cart:
        await query.edit_message_text("🛒 Giỏ hàng trống!")
    else:
        await show_cart(update, context)

# ─── Mua ngay ─────────────────────────────────────────────────
async def buy_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    prod_id = int(parts[1])
    qty = int(parts[2])

    session = db()
    try:
        user = get_or_create_user(session, update)
        p = session.query(Product).get(prod_id)

        if not p or not p.is_active:
            await query.edit_message_text("❌ Sản phẩm không tồn tại!")
            return
        if p.stock < qty:
            await query.edit_message_text(f"❌ Chỉ còn {p.stock} sản phẩm!")
            return

        total = p.price * qty
        if user.balance < total:
            shortage = total - user.balance
            await query.edit_message_text(
                f"❌ *Số dư không đủ!*\n\n"
                f"💰 Số dư hiện tại: *{fmt_price(user.balance)}*\n"
                f"💸 Cần thanh toán: *{fmt_price(total)}*\n"
                f"⚠️ Thiếu: *{fmt_price(shortage)}*\n\n"
                f"Vui lòng nạp thêm tiền và thử lại.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💰 Nạp tiền ngay", callback_data="go_deposit")
                ]])
            )
            return

        # Process purchase
        await _process_purchase(query, session, user, [(p, qty)])
    finally:
        session.close()

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cart = get_cart(context)
    if not cart:
        await query.edit_message_text("🛒 Giỏ hàng trống!")
        return

    session = db()
    try:
        user = get_or_create_user(session, update)
        items = []
        total = 0
        errors = []

        for key, item in cart.items():
            p = session.query(Product).get(int(key))
            if not p or not p.is_active:
                errors.append(f"'{item['name']}' không còn tồn tại")
                continue
            if p.stock < item["qty"]:
                errors.append(f"'{p.name}' chỉ còn {p.stock} sản phẩm")
                continue
            items.append((p, item["qty"]))
            total += p.price * item["qty"]

        if errors:
            await query.edit_message_text("❌ Lỗi:\n" + "\n".join(f"• {e}" for e in errors))
            return

        if user.balance < total:
            shortage = total - user.balance
            await query.edit_message_text(
                f"❌ *Số dư không đủ!*\n\n"
                f"💰 Số dư: *{fmt_price(user.balance)}*\n"
                f"💸 Cần: *{fmt_price(total)}*\n"
                f"⚠️ Thiếu: *{fmt_price(shortage)}*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💰 Nạp tiền", callback_data="go_deposit")
                ]])
            )
            return

        await _process_purchase(query, session, user, items)
        context.user_data["cart"] = {}
    finally:
        session.close()

async def _process_purchase(query, session, user, items: list):
    """Core purchase logic: deduct balance, assign codes, create order"""
    order_code = gen_order_code()
    total = sum(p.price * qty for p, qty in items)

    # Deduct balance
    bal_before = user.balance
    user.balance -= total
    user.total_spent += total

    # Create order
    order = Order(
        user_id=user.id,
        order_code=order_code,
        total_amount=total,
        status=OrderStatus.COMPLETED,
        completed_at=datetime.utcnow()
    )
    session.add(order)
    session.flush()

    # Assign codes
    result_lines = [f"✅ *Đơn hàng #{order_code} thành công!*\n"]
    for p, qty in items:
        codes = session.query(Code).filter_by(
            product_id=p.id, is_sold=False
        ).limit(qty).all()

        if len(codes) < qty:
            session.rollback()
            await query.edit_message_text(
                f"❌ Lỗi hệ thống: Không đủ mã cho '{p.name}'. Vui lòng liên hệ support!"
            )
            return

        code_values = []
        for code in codes:
            code.is_sold = True
            code.sold_at = datetime.utcnow()
            code.order_item_id = order.id
            p.stock -= 1
            code_values.append(code.code_value)

        item = OrderItem(
            order_id=order.id,
            product_id=p.id,
            quantity=qty,
            unit_price=p.price,
            codes_delivered=json.dumps(code_values)
        )
        session.add(item)

        result_lines.append(f"📦 *{p.name}* (x{qty}):")
        for i, cv in enumerate(code_values, 1):
            result_lines.append(f"`{cv}`")

    # Transaction record
    txn = Transaction(
        user_id=user.id,
        type=TransactionType.PURCHASE,
        amount=-total,
        balance_before=bal_before,
        balance_after=user.balance,
        description=f"Mua hàng #{order_code}",
        reference=order_code
    )
    session.add(txn)
    session.commit()

    result_lines.append(f"\n💰 Số dư còn lại: *{fmt_price(user.balance)}*")
    result_lines.append(f"\n⚠️ _Lưu lại thông tin ngay! Bot không lưu mật khẩu lần 2._")

    await query.edit_message_text(
        "\n".join(result_lines),
        parse_mode=ParseMode.MARKDOWN
    )

# ─── Đơn hàng ──────────────────────────────────────────────────
async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = db()
    try:
        user = get_or_create_user(session, update)
        orders = session.query(Order).filter_by(
            user_id=user.id
        ).order_by(Order.created_at.desc()).limit(10).all()

        if not orders:
            await update.message.reply_text(
                "📦 *Lịch sử đơn hàng*\n\nBạn chưa có đơn hàng nào.",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        lines = ["📦 *Lịch sử đơn hàng gần đây*\n"]
        keyboard = []
        for o in orders:
            status_icon = {"completed": "✅", "pending": "⏳", "cancelled": "❌"}.get(o.status.value, "❓")
            lines.append(
                f"{status_icon} #{o.order_code} | {fmt_price(o.total_amount)} | "
                f"{o.created_at.strftime('%d/%m %H:%M')}"
            )
            keyboard.append([InlineKeyboardButton(
                f"#{o.order_code} - {fmt_price(o.total_amount)}",
                callback_data=f"order_{o.id}"
            )])

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    finally:
        session.close()

async def show_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[1])

    session = db()
    try:
        order = session.query(Order).get(order_id)
        user = get_or_create_user(session, update)
        if not order or order.user_id != user.id:
            await query.edit_message_text("❌ Không tìm thấy đơn hàng!")
            return

        lines = [f"📦 *Chi tiết đơn hàng #{order.order_code}*\n"]
        lines.append(f"📅 Ngày: {order.created_at.strftime('%d/%m/%Y %H:%M')}")
        lines.append(f"💰 Tổng tiền: {fmt_price(order.total_amount)}\n")

        for item in order.items:
            lines.append(f"*{item.product.name}* x{item.quantity}:")
            codes = json.loads(item.codes_delivered or "[]")
            for c in codes:
                lines.append(f"`{c}`")
            lines.append("")

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Quay lại", callback_data="back_orders")
            ]])
        )
    finally:
        session.close()

# ─── Nạp tiền ──────────────────────────────────────────────────
async def show_deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"💰 *Nạp tiền vào tài khoản*\n\n"
        f"🏦 Ngân hàng: *{config.BANK_NAME}*\n"
        f"💳 Số tài khoản: `{config.BANK_ACCOUNT}`\n"
        f"👤 Chủ tài khoản: *{config.BANK_OWNER}*\n\n"
        f"📝 *Hướng dẫn nạp tiền:*\n"
        f"1️⃣ Nhập số tiền cần nạp\n"
        f"2️⃣ Bot sẽ cung cấp mã chuyển khoản\n"
        f"3️⃣ Chuyển khoản đúng nội dung\n"
        f"4️⃣ Admin xác nhận trong vòng 5 phút\n\n"
        f"⚠️ Nạp tối thiểu: *{fmt_price(config.MIN_DEPOSIT)}*\n\n"
        f"💬 Nhập số tiền muốn nạp:"
    )
    if update.message:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    elif update.callback_query:
        await update.callback_query.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    return DEPOSIT_AMOUNT

async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "").replace(".", "")
    try:
        amount = int(text)
    except ValueError:
        await update.message.reply_text("❌ Vui lòng nhập số tiền hợp lệ (VD: 50000)")
        return DEPOSIT_AMOUNT

    if amount < config.MIN_DEPOSIT:
        await update.message.reply_text(
            f"❌ Số tiền tối thiểu là {fmt_price(config.MIN_DEPOSIT)}!"
        )
        return DEPOSIT_AMOUNT

    session = db()
    try:
        user = get_or_create_user(session, update)
        transfer_code = gen_transfer_code(user.telegram_id)

        deposit = DepositRequest(
            user_id=user.id,
            telegram_id=user.telegram_id,
            amount=amount,
            transfer_code=transfer_code
        )
        session.add(deposit)
        session.commit()

        await update.message.reply_text(
            f"💰 *Thông tin chuyển khoản*\n\n"
            f"🏦 Ngân hàng: *{config.BANK_NAME}*\n"
            f"💳 Số TK: `{config.BANK_ACCOUNT}`\n"
            f"👤 Chủ TK: *{config.BANK_OWNER}*\n"
            f"💵 Số tiền: *{fmt_price(amount)}*\n"
            f"📝 Nội dung CK: `{transfer_code}`\n\n"
            f"⚠️ *Bắt buộc ghi đúng nội dung chuyển khoản!*\n"
            f"✅ Tài khoản sẽ được cộng tiền trong 5 phút sau khi admin xác nhận.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Tôi đã chuyển khoản", callback_data=f"deposited_{deposit.id}"),
                InlineKeyboardButton("❌ Hủy", callback_data=f"canceldeposit_{deposit.id}")
            ]])
        )
        return ConversationHandler.END
    finally:
        session.close()

async def deposit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("deposited_"):
        deposit_id = int(data.split("_")[1])
        session = db()
        try:
            dep = session.query(DepositRequest).get(deposit_id)
            if dep:
                await query.edit_message_text(
                    f"✅ *Đã ghi nhận yêu cầu nạp tiền!*\n\n"
                    f"💵 Số tiền: *{fmt_price(dep.amount)}*\n"
                    f"📝 Mã GD: `{dep.transfer_code}`\n\n"
                    f"⏳ Admin sẽ xác nhận trong vòng 5 phút.\n"
                    f"💬 Nếu sau 15 phút chưa nhận tiền, liên hệ {config.SUPPORT_USERNAME}",
                    parse_mode=ParseMode.MARKDOWN
                )
                # Notify admins
                for admin_id in config.ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"💰 *YÊU CẦU NẠP TIỀN MỚI*\n\n"
                            f"👤 User: [{dep.user.full_name}](tg://user?id={dep.telegram_id})\n"
                            f"🆔 TG ID: `{dep.telegram_id}`\n"
                            f"💵 Số tiền: *{fmt_price(dep.amount)}*\n"
                            f"📝 Mã CK: `{dep.transfer_code}`\n"
                            f"🕐 Lúc: {dep.created_at.strftime('%H:%M %d/%m/%Y')}",
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("✅ Xác nhận", callback_data=f"adminconfirm_{dep.id}"),
                                InlineKeyboardButton("❌ Từ chối", callback_data=f"adminreject_{dep.id}")
                            ]])
                        )
                    except Exception:
                        pass
        finally:
            session.close()

    elif data.startswith("canceldeposit_"):
        deposit_id = int(data.split("_")[1])
        session = db()
        try:
            dep = session.query(DepositRequest).get(deposit_id)
            if dep and dep.status == "pending":
                dep.status = "rejected"
                session.commit()
            await query.edit_message_text("❌ Đã hủy yêu cầu nạp tiền.")
        finally:
            session.close()

    elif data == "go_deposit":
        await query.message.reply_text(
            f"💬 Nhập số tiền muốn nạp (tối thiểu {fmt_price(config.MIN_DEPOSIT)}):"
        )
        context.user_data["awaiting_deposit"] = True

# ─── Admin deposit confirm ─────────────────────────────────────
async def admin_confirm_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(update.effective_user.id):
        await query.answer("❌ Không có quyền!", show_alert=True)
        return

    data = query.data
    deposit_id = int(data.split("_")[1])
    action = "confirm" if "confirm" in data else "reject"

    session = db()
    try:
        dep = session.query(DepositRequest).get(deposit_id)
        if not dep or dep.status != "pending":
            await query.edit_message_text("⚠️ Yêu cầu này đã được xử lý rồi!")
            return

        if action == "confirm":
            dep.status = "confirmed"
            dep.confirmed_at = datetime.utcnow()
            dep.confirmed_by = str(update.effective_user.id)

            user = dep.user
            bal_before = user.balance
            user.balance += dep.amount

            txn = Transaction(
                user_id=user.id,
                type=TransactionType.DEPOSIT,
                amount=dep.amount,
                balance_before=bal_before,
                balance_after=user.balance,
                description=f"Nạp tiền - {dep.transfer_code}",
                reference=dep.transfer_code,
                confirmed_by=str(update.effective_user.id)
            )
            session.add(txn)
            session.commit()

            await query.edit_message_text(
                f"✅ *Đã xác nhận nạp tiền*\n"
                f"💵 {fmt_price(dep.amount)} → {dep.user.full_name}"
            )
            try:
                await context.bot.send_message(
                    dep.telegram_id,
                    f"✅ *Nạp tiền thành công!*\n\n"
                    f"💵 Số tiền: *{fmt_price(dep.amount)}*\n"
                    f"💰 Số dư hiện tại: *{fmt_price(user.balance)}*\n\n"
                    f"Cảm ơn bạn đã sử dụng dịch vụ! 🙏",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
        else:
            dep.status = "rejected"
            dep.confirmed_by = str(update.effective_user.id)
            session.commit()
            await query.edit_message_text(f"❌ Đã từ chối nạp tiền #{dep.transfer_code}")
            try:
                await context.bot.send_message(
                    dep.telegram_id,
                    f"❌ *Yêu cầu nạp tiền bị từ chối!*\n\n"
                    f"Mã GD: `{dep.transfer_code}`\n"
                    f"Vui lòng liên hệ {config.SUPPORT_USERNAME} để được hỗ trợ.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
    finally:
        session.close()

# ─── Tài khoản ─────────────────────────────────────────────────
async def show_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = db()
    try:
        user = get_or_create_user(session, update)
        order_count = session.query(Order).filter_by(
            user_id=user.id, status=OrderStatus.COMPLETED
        ).count()

        bot_link = f"https://t.me/{(await context.bot.get_me()).username}?start={user.referral_code}"

        await update.message.reply_text(
            f"👤 *Thông tin tài khoản*\n\n"
            f"🆔 ID: `{user.telegram_id}`\n"
            f"👤 Tên: *{user.full_name}*\n"
            f"📱 Username: @{user.username or 'chưa đặt'}\n"
            f"💰 Số dư: *{fmt_price(user.balance)}*\n"
            f"💸 Tổng chi tiêu: *{fmt_price(user.total_spent)}*\n"
            f"📦 Đơn hàng: *{order_count}*\n"
            f"📅 Ngày đăng ký: {user.created_at.strftime('%d/%m/%Y')}\n\n"
            f"🎁 *Link giới thiệu:*\n`{bot_link}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💰 Lịch sử giao dịch", callback_data="txn_history")
            ]])
        )
    finally:
        session.close()

async def show_txn_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    session = db()
    try:
        user = get_or_create_user(session, update)
        txns = session.query(Transaction).filter_by(
            user_id=user.id
        ).order_by(Transaction.created_at.desc()).limit(10).all()

        if not txns:
            await query.edit_message_text("💳 Chưa có giao dịch nào.")
            return

        lines = ["💳 *Lịch sử giao dịch*\n"]
        for t in txns:
            icon = "⬆️" if t.amount > 0 else "⬇️"
            lines.append(
                f"{icon} {fmt_price(abs(t.amount))} | {t.description[:30]} | "
                f"{t.created_at.strftime('%d/%m %H:%M')}"
            )

        await query.edit_message_text(
            "\n".join(lines), parse_mode=ParseMode.MARKDOWN
        )
    finally:
        session.close()

# ─── Hỗ trợ ────────────────────────────────────────────────────
async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📞 *Hỗ trợ khách hàng*\n\n"
        f"💬 Admin: {config.SUPPORT_USERNAME}\n"
        f"⏰ Hỗ trợ: 8h00 - 23h00 hàng ngày\n\n"
        f"📝 Nhập nội dung cần hỗ trợ, chúng tôi sẽ phản hồi sớm nhất!",
        parse_mode=ParseMode.MARKDOWN
    )
    return SUPPORT_MESSAGE

async def receive_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = db()
    try:
        user = get_or_create_user(session, update)
        msg = update.message.text

        for admin_id in config.ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"📩 *Tin nhắn hỗ trợ mới*\n\n"
                    f"👤 [{user.full_name}](tg://user?id={user.telegram_id})\n"
                    f"🆔 `{user.telegram_id}`\n"
                    f"💬 Nội dung: {msg}",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📩 Trả lời", url=f"tg://user?id={user.telegram_id}")
                    ]])
                )
            except Exception:
                pass

        await update.message.reply_text(
            "✅ Đã gửi tin nhắn! Admin sẽ phản hồi sớm nhất có thể.",
            reply_markup=main_keyboard(is_admin(update.effective_user.id))
        )
        return ConversationHandler.END
    finally:
        session.close()

# ─── Admin Panel Link ──────────────────────────────────────────
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        f"⚙️ *Admin Panel*\n\n"
        f"🌐 Truy cập: http://YOUR_SERVER_IP:{config.ADMIN_PORT}/admin\n\n"
        f"📊 Xem đơn hàng, quản lý sản phẩm, xác nhận nạp tiền tại trang web admin.",
        parse_mode=ParseMode.MARKDOWN
    )

# ─── Admin Bot Commands ────────────────────────────────────────
async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Dùng: /broadcast <nội dung>")
        return

    msg = " ".join(context.args)
    session = db()
    try:
        users = session.query(User).filter_by(is_banned=False).all()
        success = 0
        for u in users:
            try:
                await context.bot.send_message(u.telegram_id, f"📢 *Thông báo*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
                success += 1
            except Exception:
                pass
        await update.message.reply_text(f"✅ Đã gửi tới {success}/{len(users)} users")
    finally:
        session.close()

async def admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Dùng: /addbalance <telegram_id> <số_tiền>")
        return
    session = db()
    try:
        tg_id = context.args[0]
        amount = float(context.args[1])
        user = session.query(User).filter_by(telegram_id=tg_id).first()
        if not user:
            await update.message.reply_text("❌ Không tìm thấy user!")
            return
        bal_before = user.balance
        user.balance += amount
        txn = Transaction(
            user_id=user.id,
            type=TransactionType.DEPOSIT,
            amount=amount,
            balance_before=bal_before,
            balance_after=user.balance,
            description="Admin thêm tiền",
            confirmed_by=str(update.effective_user.id)
        )
        session.add(txn)
        session.commit()
        await update.message.reply_text(f"✅ Đã thêm {fmt_price(amount)} cho {user.full_name}")
        await context.bot.send_message(
            tg_id,
            f"✅ Tài khoản được cộng *{fmt_price(amount)}*\nSố dư: *{fmt_price(user.balance)}*",
            parse_mode=ParseMode.MARKDOWN
        )
    finally:
        session.close()

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    session = db()
    try:
        total_users = session.query(User).count()
        total_orders = session.query(Order).filter_by(status=OrderStatus.COMPLETED).count()
        total_revenue = session.query(Order).filter_by(status=OrderStatus.COMPLETED).all()
        revenue = sum(o.total_amount for o in total_revenue)
        pending_deposits = session.query(DepositRequest).filter_by(status="pending").count()

        await update.message.reply_text(
            f"📊 *Thống kê Bot*\n\n"
            f"👥 Tổng users: *{total_users}*\n"
            f"📦 Tổng đơn hàng: *{total_orders}*\n"
            f"💰 Doanh thu: *{fmt_price(revenue)}*\n"
            f"⏳ Chờ duyệt nạp: *{pending_deposits}*",
            parse_mode=ParseMode.MARKDOWN
        )
    finally:
        session.close()

# ─── Error handler ────────────────────────────────────────────
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error: {context.error}")

# ─── Sửa ở đây ──────────────────────────────────────────────────

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot alive"

def run_web():
    app_web.run(host="0.0.0.0", port=3000)

threading.Thread(target=run_web).start()

# ─── Main ─────────────────────────────────────────────────────
def main():
    session = db()
    try:
        seed_data(session)
    finally:
        session.close()

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Deposit conversation
    deposit_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💰 Nạp tiền$"), show_deposit_menu),
        ],
        states={
            DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    # Support conversation
    support_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📞 Hỗ trợ$"), show_support)],
        states={
            SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_support_message)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("addbalance", admin_add_balance))
    app.add_handler(CommandHandler("stats", admin_stats))

    # Conversations
    app.add_handler(deposit_conv)
    app.add_handler(support_conv)

    # Message handlers
    app.add_handler(MessageHandler(filters.Regex("^🛍 Sản phẩm$"), show_categories))
    app.add_handler(MessageHandler(filters.Regex("^🛒 Giỏ hàng$"), show_cart))
    app.add_handler(MessageHandler(filters.Regex("^📦 Đơn hàng$"), show_orders))
    app.add_handler(MessageHandler(filters.Regex("^👤 Tài khoản$"), show_account))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ Admin Panel$"), show_admin_panel))

    # Callbacks
    app.add_handler(CallbackQueryHandler(show_products, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(show_product_detail, pattern="^prod_"))
    app.add_handler(CallbackQueryHandler(back_to_categories, pattern="^back_cats$"))
    app.add_handler(CallbackQueryHandler(add_to_cart, pattern="^addcart_"))
    app.add_handler(CallbackQueryHandler(buy_now, pattern="^buynow_"))
    app.add_handler(CallbackQueryHandler(cart_callback, pattern="^(cartrem_|cartdec_|clearcart)"))
    app.add_handler(CallbackQueryHandler(checkout, pattern="^checkout$"))
    app.add_handler(CallbackQueryHandler(deposit_callback, pattern="^(deposited_|canceldeposit_|go_deposit)"))
    app.add_handler(CallbackQueryHandler(admin_confirm_deposit, pattern="^(adminconfirm_|adminreject_)"))
    app.add_handler(CallbackQueryHandler(show_order_detail, pattern="^order_"))
    app.add_handler(CallbackQueryHandler(show_txn_history, pattern="^txn_history$"))

    app.add_error_handler(error_handler)

    logger.info("🤖 Bot đang chạy...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
