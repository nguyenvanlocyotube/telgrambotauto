"""
Admin Web Panel - Flask App
Quản trị bot bán mã xã hội
"""
import json
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash
)
from sqlalchemy import func

import config
from models import (
    get_engine, init_db, get_session, seed_data,
    User, Category, Product, Code, Order, OrderItem,
    Transaction, DepositRequest, BotSettings,
    OrderStatus, TransactionType
)

app = Flask(__name__)
app.secret_key = config.ADMIN_SECRET_KEY

engine = get_engine(config.DATABASE_URL)
init_db(engine)

def db():
    return get_session(engine)

# ─── Auth decorator ────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ─── Auth ──────────────────────────────────────────────────────
@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (request.form["username"] == config.ADMIN_USERNAME and
                request.form["password"] == config.ADMIN_PASSWORD):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("❌ Sai tên đăng nhập hoặc mật khẩu!", "error")
    return render_template("login.html")

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── Dashboard ─────────────────────────────────────────────────
@app.route("/admin")
@app.route("/admin/dashboard")
@login_required
def dashboard():
    s = db()
    try:
        today = datetime.utcnow().date()
        week_ago = datetime.utcnow() - timedelta(days=7)

        stats = {
            "total_users": s.query(User).count(),
            "new_users_today": s.query(User).filter(
                func.date(User.created_at) == today
            ).count(),
            "total_orders": s.query(Order).filter_by(status=OrderStatus.COMPLETED).count(),
            "orders_today": s.query(Order).filter(
                func.date(Order.created_at) == today,
                Order.status == OrderStatus.COMPLETED
            ).count(),
            "total_revenue": s.query(func.sum(Order.total_amount)).filter_by(
                status=OrderStatus.COMPLETED
            ).scalar() or 0,
            "revenue_today": s.query(func.sum(Order.total_amount)).filter(
                func.date(Order.created_at) == today,
                Order.status == OrderStatus.COMPLETED
            ).scalar() or 0,
            "pending_deposits": s.query(DepositRequest).filter_by(status="pending").count(),
            "total_codes": s.query(Code).count(),
            "available_codes": s.query(Code).filter_by(is_sold=False).count(),
        }

        # Recent orders
        recent_orders = s.query(Order).order_by(
            Order.created_at.desc()
        ).limit(10).all()

        # Recent deposits
        recent_deposits = s.query(DepositRequest).order_by(
            DepositRequest.created_at.desc()
        ).limit(10).all()

        # Revenue chart data (last 7 days)
        chart_data = []
        for i in range(6, -1, -1):
            day = datetime.utcnow() - timedelta(days=i)
            rev = s.query(func.sum(Order.total_amount)).filter(
                func.date(Order.created_at) == day.date(),
                Order.status == OrderStatus.COMPLETED
            ).scalar() or 0
            chart_data.append({
                "date": day.strftime("%d/%m"),
                "revenue": int(rev)
            })

        return render_template("dashboard.html",
            stats=stats,
            recent_orders=recent_orders,
            recent_deposits=recent_deposits,
            chart_data=json.dumps(chart_data)
        )
    finally:
        s.close()

# ─── Orders ────────────────────────────────────────────────────
@app.route("/admin/orders")
@login_required
def orders():
    s = db()
    try:
        page = request.args.get("page", 1, type=int)
        status_filter = request.args.get("status", "")
        search = request.args.get("q", "")

        query = s.query(Order).join(User)
        if status_filter:
            query = query.filter(Order.status == status_filter)
        if search:
            query = query.filter(
                (Order.order_code.contains(search)) |
                (User.full_name.contains(search)) |
                (User.telegram_id.contains(search))
            )

        total = query.count()
        per_page = 20
        orders_list = query.order_by(Order.created_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        return render_template("orders.html",
            orders=orders_list,
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page,
            status_filter=status_filter,
            search=search
        )
    finally:
        s.close()

@app.route("/admin/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    s = db()
    try:
        order = s.query(Order).get(order_id)
        if not order:
            flash("Không tìm thấy đơn hàng!", "error")
            return redirect(url_for("orders"))
        items_detail = []
        for item in order.items:
            codes = json.loads(item.codes_delivered or "[]")
            items_detail.append({"item": item, "codes": codes})
        return render_template("order_detail.html", order=order, items_detail=items_detail)
    finally:
        s.close()

# ─── Products & Codes ──────────────────────────────────────────
@app.route("/admin/products")
@login_required
def products():
    s = db()
    try:
        cats = s.query(Category).order_by(Category.sort_order).all()
        cat_filter = request.args.get("cat", "")
        query = s.query(Product)
        if cat_filter:
            query = query.filter_by(category_id=cat_filter)
        products_list = query.order_by(Product.id.desc()).all()
        return render_template("products.html",
            products=products_list, categories=cats, cat_filter=cat_filter)
    finally:
        s.close()

@app.route("/admin/products/add", methods=["POST"])
@login_required
def add_product():
    s = db()
    try:
        p = Product(
            category_id=int(request.form["category_id"]),
            name=request.form["name"],
            description=request.form.get("description", ""),
            price=float(request.form["price"]),
            is_active=True,
            stock=0
        )
        s.add(p)
        s.commit()
        flash("✅ Đã thêm sản phẩm!", "success")
    except Exception as e:
        flash(f"❌ Lỗi: {e}", "error")
    finally:
        s.close()
    return redirect(url_for("products"))

@app.route("/admin/products/<int:prod_id>/toggle")
@login_required
def toggle_product(prod_id):
    s = db()
    try:
        p = s.query(Product).get(prod_id)
        if p:
            p.is_active = not p.is_active
            s.commit()
    finally:
        s.close()
    return redirect(url_for("products"))

@app.route("/admin/products/<int:prod_id>/codes")
@login_required
def product_codes(prod_id):
    s = db()
    try:
        product = s.query(Product).get(prod_id)
        if not product:
            flash("Sản phẩm không tồn tại!", "error")
            return redirect(url_for("products"))
        codes = s.query(Code).filter_by(product_id=prod_id).order_by(Code.id.desc()).limit(200).all()
        return render_template("codes.html", product=product, codes=codes)
    finally:
        s.close()

@app.route("/admin/products/<int:prod_id>/codes/add", methods=["POST"])
@login_required
def add_codes(prod_id):
    s = db()
    try:
        product = s.query(Product).get(prod_id)
        raw = request.form.get("codes", "")
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        added = 0
        for line in lines:
            existing = s.query(Code).filter_by(product_id=prod_id, code_value=line).first()
            if not existing:
                code = Code(product_id=prod_id, code_value=line)
                s.add(code)
                product.stock += 1
                added += 1
        s.commit()
        flash(f"✅ Đã thêm {added} mã!", "success")
    except Exception as e:
        flash(f"❌ Lỗi: {e}", "error")
    finally:
        s.close()
    return redirect(url_for("product_codes", prod_id=prod_id))

@app.route("/admin/products/<int:prod_id>/codes/delete-all-available", methods=["POST"])
@login_required
def delete_available_codes(prod_id):
    s = db()
    try:
        product = s.query(Product).get(prod_id)
        deleted = s.query(Code).filter_by(product_id=prod_id, is_sold=False).delete()
        product.stock = 0
        s.commit()
        flash(f"✅ Đã xóa {deleted} mã chưa bán!", "success")
    finally:
        s.close()
    return redirect(url_for("product_codes", prod_id=prod_id))

# ─── Categories ────────────────────────────────────────────────
@app.route("/admin/categories", methods=["GET", "POST"])
@login_required
def categories():
    s = db()
    try:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                cat = Category(
                    name=request.form["name"],
                    emoji=request.form.get("emoji", "📦"),
                    description=request.form.get("description", ""),
                    sort_order=int(request.form.get("sort_order", 99))
                )
                s.add(cat)
                s.commit()
                flash("✅ Đã thêm danh mục!", "success")
            elif action == "delete":
                cat_id = int(request.form["id"])
                s.query(Category).filter_by(id=cat_id).delete()
                s.commit()
                flash("✅ Đã xóa danh mục!", "success")

        cats = s.query(Category).order_by(Category.sort_order).all()
        return render_template("categories.html", categories=cats)
    finally:
        s.close()

# ─── Users ─────────────────────────────────────────────────────
@app.route("/admin/users")
@login_required
def users():
    s = db()
    try:
        search = request.args.get("q", "")
        page = request.args.get("page", 1, type=int)
        query = s.query(User)
        if search:
            query = query.filter(
                (User.full_name.contains(search)) |
                (User.telegram_id.contains(search)) |
                (User.username.contains(search))
            )
        total = query.count()
        per_page = 20
        users_list = query.order_by(User.created_at.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        return render_template("users.html",
            users=users_list, total=total, page=page,
            per_page=per_page, pages=(total + per_page - 1) // per_page,
            search=search
        )
    finally:
        s.close()

@app.route("/admin/users/<int:user_id>")
@login_required
def user_detail(user_id):
    s = db()
    try:
        user = s.query(User).get(user_id)
        if not user:
            flash("Không tìm thấy user!", "error")
            return redirect(url_for("users"))
        orders = s.query(Order).filter_by(user_id=user_id).order_by(
            Order.created_at.desc()).limit(20).all()
        transactions = s.query(Transaction).filter_by(user_id=user_id).order_by(
            Transaction.created_at.desc()).limit(20).all()
        return render_template("user_detail.html",
            user=user, orders=orders, transactions=transactions)
    finally:
        s.close()

@app.route("/admin/users/<int:user_id>/ban", methods=["POST"])
@login_required
def ban_user(user_id):
    s = db()
    try:
        user = s.query(User).get(user_id)
        if user:
            user.is_banned = not user.is_banned
            s.commit()
            status = "cấm" if user.is_banned else "bỏ cấm"
            flash(f"✅ Đã {status} user {user.full_name}!", "success")
    finally:
        s.close()
    return redirect(url_for("user_detail", user_id=user_id))

@app.route("/admin/users/<int:user_id>/add-balance", methods=["POST"])
@login_required
def admin_add_balance_web(user_id):
    s = db()
    try:
        user = s.query(User).get(user_id)
        amount = float(request.form.get("amount", 0))
        note = request.form.get("note", "Admin cộng tiền")
        if user and amount != 0:
            bal_before = user.balance
            user.balance += amount
            txn = Transaction(
                user_id=user.id,
                type=TransactionType.DEPOSIT if amount > 0 else TransactionType.REFUND,
                amount=amount,
                balance_before=bal_before,
                balance_after=user.balance,
                description=note,
                confirmed_by="admin_web"
            )
            s.add(txn)
            s.commit()
            flash(f"✅ Đã {'cộng' if amount > 0 else 'trừ'} {abs(amount):,.0f}đ!", "success")
    except Exception as e:
        flash(f"❌ Lỗi: {e}", "error")
    finally:
        s.close()
    return redirect(url_for("user_detail", user_id=user_id))

# ─── Deposits ──────────────────────────────────────────────────
@app.route("/admin/deposits")
@login_required
def deposits():
    s = db()
    try:
        status_filter = request.args.get("status", "pending")
        page = request.args.get("page", 1, type=int)
        query = s.query(DepositRequest)
        if status_filter:
            query = query.filter_by(status=status_filter)
        total = query.count()
        per_page = 20
        deps = query.order_by(DepositRequest.created_at.desc()).offset(
            (page - 1) * per_page).limit(per_page).all()
        return render_template("deposits.html",
            deposits=deps, total=total, page=page,
            per_page=per_page, pages=(total + per_page - 1) // per_page,
            status_filter=status_filter
        )
    finally:
        s.close()

@app.route("/admin/deposits/<int:dep_id>/confirm", methods=["POST"])
@login_required
def confirm_deposit(dep_id):
    s = db()
    try:
        dep = s.query(DepositRequest).get(dep_id)
        if dep and dep.status == "pending":
            dep.status = "confirmed"
            dep.confirmed_at = datetime.utcnow()
            dep.confirmed_by = "admin_web"
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
                confirmed_by="admin_web"
            )
            s.add(txn)
            s.commit()
            flash(f"✅ Đã xác nhận nạp {dep.amount:,.0f}đ cho {user.full_name}!", "success")
        else:
            flash("⚠️ Yêu cầu này đã được xử lý!", "warning")
    finally:
        s.close()
    return redirect(url_for("deposits"))

@app.route("/admin/deposits/<int:dep_id>/reject", methods=["POST"])
@login_required
def reject_deposit(dep_id):
    s = db()
    try:
        dep = s.query(DepositRequest).get(dep_id)
        if dep and dep.status == "pending":
            dep.status = "rejected"
            dep.confirmed_by = "admin_web"
            s.commit()
            flash("✅ Đã từ chối yêu cầu nạp tiền!", "success")
    finally:
        s.close()
    return redirect(url_for("deposits"))

# ─── Settings ──────────────────────────────────────────────────
@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def settings():
    s = db()
    try:
        if request.method == "POST":
            keys = ["welcome_message", "maintenance_mode", "maintenance_message",
                    "min_deposit", "bonus_rate"]
            for key in keys:
                val = request.form.get(key, "")
                existing = s.query(BotSettings).filter_by(key=key).first()
                if existing:
                    existing.value = val
                    existing.updated_at = datetime.utcnow()
                else:
                    s.add(BotSettings(key=key, value=val))
            s.commit()
            flash("✅ Đã lưu cài đặt!", "success")

        all_settings = {row.key: row.value for row in s.query(BotSettings).all()}
        return render_template("settings.html", settings=all_settings)
    finally:
        s.close()

# ─── API endpoints for AJAX ────────────────────────────────────
@app.route("/admin/api/stats")
@login_required
def api_stats():
    s = db()
    try:
        today = datetime.utcnow().date()
        return jsonify({
            "pending_deposits": s.query(DepositRequest).filter_by(status="pending").count(),
            "orders_today": s.query(Order).filter(
                func.date(Order.created_at) == today,
                Order.status == OrderStatus.COMPLETED
            ).count(),
        })
    finally:
        s.close()

# ─── Template filters ──────────────────────────────────────────
@app.template_filter("fmt_price")
def fmt_price_filter(amount):
    if amount is None:
        return "0đ"
    return f"{int(amount):,}đ"

@app.template_filter("fmt_date")
def fmt_date_filter(dt):
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M")

@app.template_filter("status_badge")
def status_badge_filter(status):
    badges = {
        "completed": '<span class="badge bg-success">Hoàn thành</span>',
        "pending": '<span class="badge bg-warning text-dark">Chờ xử lý</span>',
        "cancelled": '<span class="badge bg-danger">Đã hủy</span>',
        "confirmed": '<span class="badge bg-success">Đã xác nhận</span>',
        "rejected": '<span class="badge bg-danger">Từ chối</span>',
    }
    val = status.value if hasattr(status, "value") else str(status)
    return badges.get(val, f'<span class="badge bg-secondary">{val}</span>')

if __name__ == "__main__":
    s = db()
    try:
        seed_data(s)
    finally:
        s.close()
    app.run(host="0.0.0.0", port=config.ADMIN_PORT, debug=False)
