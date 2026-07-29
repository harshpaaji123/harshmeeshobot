import os
import sqlite3
import qrcode
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, 
    filters, ContextTypes, ConversationHandler
)

# ================= CONFIGURATION =================
TOKEN = "8973528979:AAGz1mp2bfRARk5uUZGVF2V6EjxDF92aAE4"
DEFAULT_UPI_ID = "bharatpe.8y0l1s2n7z76332@fbpe"
ADMIN_ID = 5573430719  # Screenshot ke hisab se updated (Agar different hai toh apni ID daalna)
CUSTOM_QR_PATH = "custom_qr.png"

# Conversation States
(
    AWAITING_COUPON,
    AWAITING_KEY_ADD,
    AWAITING_COUPON_ADD,
    AWAITING_BLOCK_USER,
    AWAITING_PRODUCT_ADD,
    AWAITING_PRICE_EDIT,
    AWAITING_NEW_UPI,
    AWAITING_NEW_QR,
    AWAITING_BINANCE_LINK
) = range(1, 10)

# Default Categories & Products structure (With USD $)
DEFAULT_PRODUCTS = {
    "💎 Fluorite Keys": [
        ("7 DAY KEY | 900 INR | 9$", "Fluorite 7 Day Key", 900),
        ("1 MONTH KEY | 1500 INR | 15$", "Fluorite 1 Month Key", 1500)
    ],
    "🤖 Android Keys": [
        ("7 DAY KEY | 600 INR | 6$", "Android 7 Day Key", 600),
        ("1 MONTH KEY | 1000 INR | 10$", "Android 1 Month Key", 1000),
        ("FULL SEASON KEY | 2000 INR | 20$", "Android Full Season Key", 2000)
    ],
    "📱 Full iOS Panel": [
        ("FULL IOS PANEL | 3000 INR | 30$", "Full iOS Panel", 3000)
    ],
    "🛠️ Full Android Panel": [
        ("FULL ANDROID PANEL | 2000 INR | 20$", "Full Android Panel", 2000)
    ],
    "📦 GBox": [
        ("GBOX 6 MONTH | 1000 INR | 10$", "GBox 6 Month", 1000),
        ("GBOX 1 YEAR | 1500 INR | 15$", "GBox 1 Year", 1500)
    ],
    "✍️ Esign": [
        ("ESIGN 1 YEAR CERTIFICATE | 800 INR | 8$", "Esign 1 Year Certificate", 800)
    ],
    "🔑 Monite Key": [
        ("7 DAY KEY | 600 INR | 6$", "Monite 7 Day Key", 600),
        ("31 DAYS KEY | 1000 INR | 10$", "Monite 31 Days Key", 1000)
    ]
}

# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect("shop_data.db")
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_code TEXT UNIQUE,
                        status TEXT DEFAULT 'AVAILABLE'
                    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS coupons (
                        code TEXT PRIMARY KEY,
                        discount INT
                    )''')
                    
    cursor.execute('''CREATE TABLE IF NOT EXISTS blocked_users (
                        user_id TEXT PRIMARY KEY
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INT,
                        item TEXT,
                        amount INT,
                        status TEXT
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT,
                        btn_label TEXT,
                        item_name TEXT,
                        price INT
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )''')

    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('upi_id', ?)", (DEFAULT_UPI_ID,))

    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        for cat, items in DEFAULT_PRODUCTS.items():
            for label, item_name, price in items:
                cursor.execute(
                    "INSERT INTO products (category, btn_label, item_name, price) VALUES (?, ?, ?, ?)",
                    (cat, label, item_name, price)
                )

    default_coupons = [
        ("IOSKEY300D", 300), ("KEYS200D", 200), 
        ("VIPOFF500D", 500), ("PROMO100D", 100), ("SAVE400D", 400)
    ]
    for code, disc in default_coupons:
        cursor.execute("INSERT OR IGNORE INTO coupons VALUES (?, ?)", (code, disc))

    sample_keys = [
        "HGK38YLSF8FN0LIA", "PLM92KSHA71629AL", "OQI1827364510PLA", "ZXM9821736451290",
        "QWE1234567890RTY", "UIO0987654321PAS", "DFG6543210987JKL", "CVB7890123456MNO"
    ]
    for k in sample_keys:
        cursor.execute("INSERT OR IGNORE INTO keys (key_code) VALUES (?)", (k,))

    conn.commit()
    conn.close()

init_db()

# Settings Helpers
def get_current_upi():
    conn = sqlite3.connect("shop_data.db")
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='upi_id'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else DEFAULT_UPI_ID

def set_current_upi(new_upi):
    conn = sqlite3.connect("shop_data.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('upi_id', ?)", (new_upi,))
    conn.commit()
    conn.close()

# DB Helpers
def get_categories_from_db():
    conn = sqlite3.connect("shop_data.db")
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM products")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_products_by_category(category):
    conn = sqlite3.connect("shop_data.db")
    c = conn.cursor()
    c.execute("SELECT id, btn_label, item_name, price FROM products WHERE category=?", (category,))
    rows = c.fetchall()
    conn.close()
    return rows

def esc(text):
    if not text:
        return ""
    return str(text).replace('_', '\\_').replace('*', '\\*').replace('`', '\\`')

# ================= KEYBOARDS =================
def get_user_menu():
    kb = [
        [KeyboardButton("💎 Fluorite Keys"), KeyboardButton("🤖 Android Keys")],
        [KeyboardButton("📱 Full iOS Panel"), KeyboardButton("🛠️ Full Android Panel")],
        [KeyboardButton("📦 GBox"), KeyboardButton("✍️ Esign")],
        [KeyboardButton("🔑 Monite Key"), KeyboardButton("👤 Profile")],
        [KeyboardButton("📜 My Orders")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_admin_menu():
    kb = [
        [KeyboardButton("📦 Manage Products"), KeyboardButton("📋 Orders")],
        [KeyboardButton("🏷️ Discount Coupon"), KeyboardButton("💳 Payment Method")],
        [KeyboardButton("🚫 Block User"), KeyboardButton("❌ Exit Admin")]
    ]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_payment_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏷️ Apply Discount Coupon", callback_data="prompt_coupon")],
        [InlineKeyboardButton("📸 Upload Payment Screenshot", callback_data="prompt_upload_ss")],
        [InlineKeyboardButton("💎 PAY IN BINANCE USDT", callback_data="req_binance_pay")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="close_payment")]
    ])

# ================= COMMAND / START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    conn = sqlite3.connect("shop_data.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM blocked_users WHERE user_id=?", (user_id,))
    if c.fetchone():
        conn.close()
        await update.message.reply_text("🚫 **You are blocked from using this bot.**", parse_mode="Markdown")
        return
    conn.close()

    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("⚡ **Welcome Admin!** Select option from panel:", reply_markup=get_admin_menu())
    else:
        await update.message.reply_text("✨ **Welcome to the Shop!** Choose a product category below:", reply_markup=get_user_menu())

# ================= PHOTO SCREENSHOT FORWARDING =================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    item_name = context.user_data.get('last_item', 'Fluorite 7 Day Key')
    amount = context.user_data.get('discounted_amount', context.user_data.get('last_amount', 900))

    conn = sqlite3.connect("shop_data.db")
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, item, amount, status) VALUES (?, ?, ?, ?)", (user.id, item_name, amount, "PENDING"))
    order_id = c.lastrowid
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "⏳ **Payment Screenshot Received!**\n\nPlease wait up to **10 minutes** while admin verifies your payment.",
        parse_mode="Markdown"
    )

    admin_btn = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve Order", callback_data=f"appr_{order_id}_{user.id}"),
            InlineKeyboardButton("❌ Reject Order", callback_data=f"rejc_{order_id}_{user.id}")
        ]
    ])

    username_str = f"(@{esc(user.username)})" if user.username else ""
    full_name = esc(user.first_name)
    if user.last_name:
        full_name += f" {esc(user.last_name)}"

    admin_caption = (
        f"🔔 **Incoming Store Purchase Request!**\n\n"
        f"👤 **Client:** {full_name} {username_str}\n"
        f"🆔 **User ID:** `{user.id}`\n"
        f"📦 **Product:** {esc(item_name)}\n"
        f"💰 **Transferred:** {amount} INR"
    )

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=update.message.photo[-1].file_id,
        caption=admin_caption,
        parse_mode="Markdown",
        reply_markup=admin_btn
    )

# ================= TEXT HANDLER =================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    conn = sqlite3.connect("shop_data.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM blocked_users WHERE user_id=?", (str(user_id),))
    if c.fetchone():
        conn.close()
        await update.message.reply_text("🚫 **You are blocked.**")
        return
    conn.close()

    # Admin Menu Options
    if user_id == ADMIN_ID:
        if text == "📦 Manage Products":
            categories = get_categories_from_db()
            kb = []
            for cat in categories:
                kb.append([InlineKeyboardButton(f"📁 {cat}", callback_data=f"admcat_{cat}")])
            
            kb.append([InlineKeyboardButton("➕ Add Key Stock", callback_data="admin_add_key"), InlineKeyboardButton("➖ Remove Key Stock", callback_data="admin_rem_key")])
            await update.message.reply_text("📦 **Manage Product Categories & Price List:**\n\nSelect a category to edit prices or add new products:", reply_markup=InlineKeyboardMarkup(kb))
            return

        elif text == "📋 Orders":
            conn = sqlite3.connect("shop_data.db")
            c = conn.cursor()
            c.execute("SELECT order_id, user_id, item, amount, status FROM orders WHERE status='PENDING' ORDER BY order_id DESC LIMIT 5")
            rows = c.fetchall()
            conn.close()

            if not rows:
                await update.message.reply_text("📋 No pending orders right now.", parse_mode="Markdown")
                return

            for r in rows:
                ord_id, u_id, item, amt, st = r
                admin_btn = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Approve Order", callback_data=f"appr_{ord_id}_{u_id}"),
                     InlineKeyboardButton("❌ Reject Order", callback_data=f"rejc_{ord_id}_{u_id}")]
                ])
                msg = (
                    f"📋 **Order #{ord_id}**\n\n"
                    f"👤 **User ID:** `{u_id}`\n"
                    f"📦 **Product:** {esc(item)}\n"
                    f"💰 **Transferred:** {amt} INR\n"
                    f"Status: **{st}**"
                )
                await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=admin_btn)
            return

        elif text == "🏷️ Discount Coupon":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Coupon", callback_data="admin_add_coupon"), InlineKeyboardButton("➖ Remove Coupon", callback_data="admin_rem_coupon")]
            ])
            await update.message.reply_text("🏷️ **Manage Discount Coupons:**", reply_markup=kb)
            return

        elif text == "💳 Payment Method":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit UPI ID", callback_data="admin_edit_upi"), InlineKeyboardButton("🖼️ Change QR", callback_data="admin_change_qr")]
            ])
            current_upi = get_current_upi()
            await update.message.reply_text(f"💳 **Payment Method Configuration:**\n\nCurrent UPI ID: `{current_upi}`", parse_mode="Markdown", reply_markup=kb)
            return

        elif text == "🚫 Block User":
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Enter User ID/Username to Block", callback_data="admin_block_prompt")]])
            await update.message.reply_text("🚫 **Block User Panel:**", reply_markup=kb)
            return

        elif text == "❌ Exit Admin":
            await update.message.reply_text("Returned to User Menu.", reply_markup=get_user_menu())
            return

    # Customer Options
    categories = get_categories_from_db()

    if text in categories:
        products = get_products_by_category(text)
        kb = []
        for p_id, btn_label, item_name, price in products:
            cb_data = f"pay_{item_name}_{price}"
            kb.append([InlineKeyboardButton(btn_label, callback_data=cb_data)])
        
        await update.message.reply_text(f"Select option for {text}:", reply_markup=InlineKeyboardMarkup(kb))

    elif text == "👤 Profile":
        user = update.effective_user
        profile_text = f"👤 **User Profile Info**\n\n• **Name:** {esc(user.first_name)}\n• **Username:** @{esc(user.username) if user.username else 'N/A'}\n• **User ID:** `{user.id}`"
        await update.message.reply_text(profile_text, parse_mode="Markdown")

    elif text == "📜 My Orders":
        conn = sqlite3.connect("shop_data.db")
        c = conn.cursor()
        c.execute("SELECT order_id, item, amount, status FROM orders WHERE user_id=? ORDER BY order_id DESC LIMIT 5", (user_id,))
        rows = c.fetchall()
        conn.close()

        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="close_payment")]])

        if not rows:
            await update.message.reply_text("📜 **Your Order History**\n\nYou haven't placed any orders yet!", parse_mode="Markdown", reply_markup=back_kb)
            return

        orders_msg = "📜 **Your Recent Purchase History:**\n\n"
        for r in rows:
            ord_id, item, amt, status = r
            status_icon = "🟢" if status == "APPROVED" else ("🔴" if status == "REJECTED" else "⏳")
            orders_msg += (
                f"🆔 **Order ID:** #{ord_id}\n"
                f"📦 **Product:** {esc(item)}\n"
                f"💰 **Amount Paid:** ₹{amt}\n"
                f"📌 **Status:** {status_icon} `{status}`\n"
                f"-----------------------------------\n"
            )

        await update.message.reply_text(orders_msg, parse_mode="Markdown", reply_markup=back_kb)

# ================= BUTTON CALLBACK ROUTER =================
async def button_tap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "close_payment":
        await query.answer("Returned to Main Menu")
        await query.message.delete()

    elif data == "prompt_upload_ss":
        await query.answer()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="close_payment")]])
        await query.message.reply_text("📸 **Please share the payment screenshot in the chat now:**", parse_mode="Markdown", reply_markup=kb)

    elif data == "prompt_coupon":
        await query.answer()
        await query.message.reply_text("🏷️ **Please enter your discount coupon code in chat:**", parse_mode="Markdown")
        return AWAITING_COUPON

    elif data == "show_updated_payment":
        await query.answer()
        item_name = context.user_data.get('last_item', 'Product')
        amount = context.user_data.get('discounted_amount', context.user_data.get('last_amount', 0))
        discount = context.user_data.get('discount_saved', 0)
        await send_payment_qr(query.message.chat_id, context, item_name, amount, query.message, discount_applied=discount)

    elif data.startswith("pay_"):
        await query.answer()
        _, item_name, amount = data.split("_")
        context.user_data['last_item'] = item_name
        context.user_data['last_amount'] = int(amount)
        context.user_data['discounted_amount'] = int(amount)
        context.user_data['discount_saved'] = 0
        await send_payment_qr(query.message.chat_id, context, item_name, int(amount), query.message)

    # BINANCE USDT PAYMENT LINK REQUEST
    elif data == "req_binance_pay":
        await query.answer()
        user = query.from_user
        item_name = context.user_data.get('last_item', 'Product')
        amount = context.user_data.get('discounted_amount', context.user_data.get('last_amount', 0))
        usd_amount = max(1, amount // 100)

        await query.message.reply_text("please wait for 10 min while we are generating the binance payment link for you")

        admin_btn = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔗 Generate & Send PAYMENT LINK", callback_data=f"genbinlink_{user.id}"),
                InlineKeyboardButton("❌ REJECT ORDER", callback_data=f"binrej_{user.id}")
            ]
        ])

        username_str = f"(@{esc(user.username)})" if user.username else ""
        full_name = esc(user.first_name)
        if user.last_name:
            full_name += f" {esc(user.last_name)}"

        admin_notice = (
            f"⚡ **Binance USDT Payment Request!**\n\n"
            f"👤 **User:** {full_name} {username_str}\n"
            f"🆔 **User ID:** `{user.id}`\n"
            f"📦 **Product:** {esc(item_name)}\n"
            f"💰 **Amount:** {amount} INR (~${usd_amount} USDT)"
        )

        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notice, parse_mode="Markdown", reply_markup=admin_btn)

    elif data.startswith("genbinlink_"):
        await query.answer()
        target_uid = data.split("_")[1]
        context.user_data['target_binance_uid'] = target_uid
        await query.message.reply_text("plz paste your generate link here in the chat")
        return AWAITING_BINANCE_LINK

    elif data.startswith("binrej_"):
        await query.answer("Order Rejected")
        target_uid = data.split("_")[1]
        
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="close_payment")]])
        rejection_text = "sorry we couldn't process your payment right now plz tryagain later"
        
        await context.bot.send_message(chat_id=int(target_uid), text=rejection_text, reply_markup=kb)
        await query.edit_message_text(f"{query.message.text}\n\n🔴 **REJECTED BY ADMIN**")

    # ADMIN PAYMENT METHOD EDIT CALLBACKS
    elif data == "admin_edit_upi":
        await query.answer()
        await query.message.reply_text("plz enter YOUR NEW UPI ID IN THE CHAT")
        return AWAITING_NEW_UPI

    elif data == "admin_change_qr":
        await query.answer()
        await query.message.reply_text("PLEASE UPLOAD YOUR NEW QR IN THE CHAT")
        return AWAITING_NEW_QR

    # ADMIN PRODUCT CATEGORY SELECTION
    elif data.startswith("admcat_"):
        await query.answer()
        category = data.split("_", 1)[1]
        products = get_products_by_category(category)
        
        msg = f"📂 **Category:** `{category}`\n\n**Current Products & Prices:**\n"
        for _, btn_label, _, price in products:
            msg += f"• {btn_label}\n"
            
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Edit Prices", callback_data=f"admeditp_{category}"), InlineKeyboardButton("➕ Add Product", callback_data=f"admaddp_{category}")]
        ])
        await query.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    elif data.startswith("admaddp_"):
        await query.answer()
        category = data.split("_", 1)[1]
        context.user_data['target_category'] = category
        await query.message.reply_text(
            f"➕ **Add Product in `{category}`**\n\n"
            f"Please enter your product with price in the chat now:\n"
            f"*(Example: `1 DAY KEY | 150 INR`)*",
            parse_mode="Markdown"
        )
        return AWAITING_PRODUCT_ADD

    elif data.startswith("admeditp_"):
        await query.answer()
        category = data.split("_", 1)[1]
        products = get_products_by_category(category)
        
        kb = []
        for p_id, btn_label, _, _ in products:
            kb.append([InlineKeyboardButton(f"✏️ {btn_label}", callback_data=f"selpedit_{p_id}")])
            
        await query.message.reply_text("Select product to edit price:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("selpedit_"):
        await query.answer()
        p_id = data.split("_")[1]
        context.user_data['target_pid'] = p_id
        await query.message.reply_text("✏️ **Please enter the new price (INR) for this product:**", parse_mode="Markdown")
        return AWAITING_PRICE_EDIT

    # APPROVE BUTTON ACTION
    elif data.startswith("appr_"):
        _, order_id, user_id = data.split("_")
        
        conn = sqlite3.connect("shop_data.db")
        c = conn.cursor()
        c.execute("SELECT id, key_code FROM keys WHERE status='AVAILABLE' LIMIT 1")
        row = c.fetchone()

        if row:
            key_id, key_code = row
            c.execute("UPDATE keys SET status='SOLD' WHERE id=?", (key_id,))
            c.execute("UPDATE orders SET status='APPROVED' WHERE order_id=?", (order_id,))
            conn.commit()
            conn.close()

            await query.answer(text="Order Approved & Key Sent!", show_alert=True)

            delivery_msg = (
                f"✅ **Payment Approved!**\n\n"
                f"Thank you for your purchase. Here is your Key:\n\n"
                f"🔑 `{key_code}`\n\n"
                f"*(Tap key code to copy)*"
            )
            await context.bot.send_message(chat_id=int(user_id), text=delivery_msg, parse_mode="Markdown")
            
            updated_caption = f"{query.message.caption}\n\n🟢 **ORDER STATE: COMPLETED & DELIVERED**"
            await query.edit_message_caption(caption=updated_caption, reply_markup=None, parse_mode="Markdown")
        else:
            conn.close()
            await query.answer(text="⚠️ OUT OF STOCK! Add keys in Admin Menu!", show_alert=True)

    # REJECT BUTTON ACTION
    elif data.startswith("rejc_"):
        _, order_id, user_id = data.split("_")
        conn = sqlite3.connect("shop_data.db")
        c = conn.cursor()
        c.execute("UPDATE orders SET status='REJECTED' WHERE order_id=?", (order_id,))
        conn.commit()
        conn.close()

        await query.answer(text="Order Rejected", show_alert=True)

        rejection_msg = "❌ **Your payment got rejected.** For information please do the right payment on given QR."
        await context.bot.send_message(chat_id=int(user_id), text=rejection_msg, parse_mode="Markdown")
        
        updated_caption = f"{query.message.caption}\n\n🔴 **ORDER STATE: REJECTED & DISMISSED**"
        await query.edit_message_caption(caption=updated_caption, reply_markup=None, parse_mode="Markdown")

    # Admin Management Callbacks
    elif data == "admin_add_key":
        await query.answer()
        await query.message.reply_text("➕ **Send the new key code in chat to add:**", parse_mode="Markdown")
        return AWAITING_KEY_ADD

    elif data == "admin_rem_key":
        await query.answer()
        conn = sqlite3.connect("shop_data.db")
        c = conn.cursor()
        c.execute("SELECT id, key_code FROM keys WHERE status='AVAILABLE' LIMIT 10")
        rows = c.fetchall()
        conn.close()

        if not rows:
            await query.message.reply_text("No keys available in stock.")
            return

        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"❌ Delete {r[1]}", callback_data=f"delkey_{r[0]}")] for r in rows])
        await query.message.reply_text("Tap key to remove:", reply_markup=kb)

    elif data.startswith("delkey_"):
        await query.answer()
        key_id = data.split("_")[1]
        conn = sqlite3.connect("shop_data.db")
        c = conn.cursor()
        c.execute("DELETE FROM keys WHERE id=?", (key_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ **Your key is successfully removed!**", parse_mode="Markdown")

    elif data == "admin_add_coupon":
        await query.answer()
        await query.message.reply_text("➕ Send coupon format in chat: `CODE:DISCOUNT` (e.g. `OFF100:100`)", parse_mode="Markdown")
        return AWAITING_COUPON_ADD

    elif data == "admin_rem_coupon":
        await query.answer()
        conn = sqlite3.connect("shop_data.db")
        c = conn.cursor()
        c.execute("SELECT code FROM coupons")
        rows = c.fetchall()
        conn.close()

        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"❌ Remove {r[0]}", callback_data=f"delcoup_{r[0]}")] for r in rows])
        await query.message.reply_text("Tap coupon code to delete:", reply_markup=kb)

    elif data.startswith("delcoup_"):
        await query.answer()
        code = data.split("_")[1]
        conn = sqlite3.connect("shop_data.db")
        c = conn.cursor()
        c.execute("DELETE FROM coupons WHERE code=?", (code,))
        conn.commit()
        conn.close()
        await query.edit_message_text(f"✅ **Coupon '{code}' removed successfully!**", parse_mode="Markdown")

    elif data == "admin_block_prompt":
        await query.answer()
        await query.message.reply_text("🚫 **Enter User ID or Username in chat to block:**", parse_mode="Markdown")
        return AWAITING_BLOCK_USER

# ================= CONVERSATION INPUT PROCESSORS =================
async def process_user_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    conn = sqlite3.connect("shop_data.db")
    c = conn.cursor()
    c.execute("SELECT discount FROM coupons WHERE code=?", (code,))
    row = c.fetchone()
    conn.close()

    if row:
        discount = row[0]
        orig_amount = context.user_data.get('last_amount', 0)
        new_amount = max(0, orig_amount - discount)
        context.user_data['discounted_amount'] = new_amount
        context.user_data['discount_saved'] = discount

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Proceed to Updated Payment Portal", callback_data="show_updated_payment")]])
        await update.message.reply_text(f"🎉 **Congratulations!** You got **Flat ₹{discount} Discount!**", parse_mode="Markdown", reply_markup=kb)
    else:
        await update.message.reply_text("❌ **Invalid Coupon Code.** Please try again.")
    return ConversationHandler.END

async def process_admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    category = context.user_data.get('target_category')

    try:
        if "|" in raw_text:
            parts = [p.strip() for p in raw_text.split("|")]
            prod_name = parts[0]
            price_digits = ''.join(filter(str.isdigit, parts[1]))
            price = int(price_digits)
        else:
            await update.message.reply_text("❌ Invalid format. Please use format like: `1 DAY KEY | 150 INR`", parse_mode="Markdown")
            return ConversationHandler.END

        usd_price = max(1, price // 100)
        btn_label = f"{prod_name.upper()} | {price} INR | {usd_price}$"
        
        clean_cat_name = category.replace("💎 ", "").replace("🤖 ", "").replace("📱 ", "").replace("🛠️ ", "").replace("📦 ", "").replace("✍️ ", "").replace("🔑 ", "").strip()
        item_name = f"{clean_cat_name} {prod_name}"

        conn = sqlite3.connect("shop_data.db")
        c = conn.cursor()
        c.execute(
            "INSERT INTO products (category, btn_label, item_name, price) VALUES (?, ?, ?, ?)",
            (category, btn_label, item_name, price)
        )
        conn.commit()
        conn.close()

        await update.message.reply_text(f"✅ **Successfully Added!**\n\n**Category:** {category}\n**Product:** {btn_label}", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("❌ Failed to add product. Make sure to use format: `1 DAY KEY | 150 INR`", parse_mode="Markdown")

    return ConversationHandler.END

async def process_admin_edit_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = update.message.text.strip()
    p_id = context.user_data.get('target_pid')

    try:
        new_price = int(''.join(filter(str.isdigit, raw_text)))
        usd_price = max(1, new_price // 100)
        
        conn = sqlite3.connect("shop_data.db")
        c = conn.cursor()
        c.execute("SELECT btn_label, item_name FROM products WHERE id=?", (p_id,))
        row = c.fetchone()
        
        if row:
            old_label, item_name = row
            duration_part = old_label.split("|")[0].strip()
            new_label = f"{duration_part} | {new_price} INR | {usd_price}$"
            
            c.execute("UPDATE products SET btn_label=?, price=? WHERE id=?", (new_label, new_price, p_id))
            conn.commit()
            await update.message.reply_text(f"✅ **Price Updated Successfully!**\n\n**New Label:** {new_label}", parse_mode="Markdown")
        conn.close()
    except Exception as e:
        await update.message.reply_text("❌ Invalid price entered. Please enter numbers only.")

    return ConversationHandler.END

async def process_admin_add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key_code = update.message.text.strip().upper()
    conn = sqlite3.connect("shop_data.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO keys (key_code) VALUES (?)", (key_code,))
        conn.commit()
        await update.message.reply_text("✅ **Your key is added successfully!**", parse_mode="Markdown")
    except:
        await update.message.reply_text("⚠️ Key already exists.")
    finally:
        conn.close()
    return ConversationHandler.END

async def process_admin_add_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        code, disc = update.message.text.strip().split(":")
        conn = sqlite3.connect("shop_data.db")
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO coupons VALUES (?, ?)", (code.upper(), int(disc)))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ **Coupon '{code.upper()}' added!**", parse_mode="Markdown")
    except:
        await update.message.reply_text("❌ Invalid format. Use `CODE:AMOUNT`.")
    return ConversationHandler.END

async def process_admin_block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.text.strip()
    conn = sqlite3.connect("shop_data.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO blocked_users VALUES (?)", (target,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🚫 **User '{target}' blocked!**", parse_mode="Markdown")
    return ConversationHandler.END

async def process_admin_edit_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_upi = update.message.text.strip()
    set_current_upi(new_upi)
    await update.message.reply_text(f"✅ **UPI ID Updated Successfully!**\n\nNew UPI ID: `{new_upi}`", parse_mode="Markdown")
    return ConversationHandler.END

async def process_admin_change_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo and not update.message.document:
        await update.message.reply_text("❌ Please upload an image/photo of the new QR code.")
        return AWAITING_NEW_QR

    if update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
    else:
        file_obj = await update.message.document.get_file()

    await file_obj.download_to_drive(CUSTOM_QR_PATH)
    await update.message.reply_text("✅ **New QR Code uploaded and set successfully!**", parse_mode="Markdown")
    return ConversationHandler.END

async def process_admin_binance_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    target_uid = context.user_data.get('target_binance_uid')

    if target_uid:
        user_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📸 Upload Payment Screenshot", callback_data="prompt_upload_ss")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="close_payment")]
        ])

        msg = (
            f"plz complete your payment through the given link below\n\n"
            f"🔗 {link}"
        )

        await context.bot.send_message(chat_id=int(target_uid), text=msg, reply_markup=user_kb)
        await update.message.reply_text("✅ Payment link sent to user successfully!")

    return ConversationHandler.END

# ================= QR PAYMENT SCREEN =================
async def send_payment_qr(chat_id, context, item_name, amount, message_obj=None, discount_applied=0):
    upi_id = get_current_upi()
    
    if os.path.exists(CUSTOM_QR_PATH):
        with open(CUSTOM_QR_PATH, 'rb') as f:
            bio = BytesIO(f.read())
            bio.name = 'qr.png'
    else:
        upi_url = f"upi://pay?pa={upi_id}&pn=StoreAdmin&am={amount}&cu=INR"
        qr = qrcode.make(upi_url)
        bio = BytesIO()
        bio.name = 'qr.png'
        qr.save(bio, 'PNG')
    
    bio.seek(0)

    caption_text = f"📌 **UPI ID:** `{upi_id}`\n*(Tap UPI ID to copy)*\n\n"
    if discount_applied > 0:
        caption_text += f"🎉 **Coupon Discount Applied:** Saved ₹{discount_applied}!\n\n"

    caption_text += (
        f"👉 **How to Pay:**\n"
        f"1. Scan the QR Code attached above or copy the UPI ID.\n"
        f"2. Complete the transfer of exactly **{amount} INR**.\n"
        f"3. Take a clear screenshot of the successful transaction confirmation screen.\n\n"
        f"⚠️ **Crucial:** Once completed, send the payment screenshot in this chat."
    )

    if message_obj:
        await message_obj.delete()
        
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=bio,
        caption=caption_text,
        parse_mode="Markdown",
        reply_markup=get_payment_buttons()
    )

# ================= MAIN FUNCTION =================
def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_tap)],
        states={
            AWAITING_COUPON: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_coupon)],
            AWAITING_KEY_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_add_key)],
            AWAITING_COUPON_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_add_coupon)],
            AWAITING_BLOCK_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_block_user)],
            AWAITING_PRODUCT_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_add_product)],
            AWAITING_PRICE_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_edit_price)],
            AWAITING_NEW_UPI: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_edit_upi)],
            AWAITING_NEW_QR: [MessageHandler((filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND, process_admin_change_qr)],
            AWAITING_BINANCE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_binance_link)],
        },
        fallbacks=[],
        per_message=False
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot is up and running...")
    app.run_polling()

if __name__ == "__main__":
    main()