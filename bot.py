import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# ==================== CONFIGURATION ====================
TOKEN = "8632214050:AAERayVRr7OoSi5IQQHJFMjGGzBP-6mhnmI"
DEFAULT_UPI_ID = "bharatpe.8y011s2n7z76332@fbpe"
ADMIN_ID = 7309568829
ADMIN_SUPPORT_USERNAME = "@blazebattleindia"
CUSTOM_QR_PATH = "my_qr.png"

# ==================== CONVERSATION STATES ====================
(
    AwaitingPaymentScreenshot,
    AwaitingCustomKeyInput,
    AwaitingCustomQuantity,
) = range(3)

# ==================== DATABASE SETUP ====================
def init_db():
    conn = sqlite3.connect("shop_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price REAL,
            stock INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            product_name TEXT,
            quantity INTEGER,
            amount REAL,
            status TEXT
        )
    """)
    
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        default_products = [
            ("Lenskart 1Year Discount Coupons", 15.0, 10),
            ("Gana Plus 3Months", 25.0, 10),
            ("Audible 2 month coupon", 20.0, 10),
            ("Meesho ₹170 OFF JSON", 40.0, 10),
            ("Meesho ₹195 OFF JSON", 60.0, 10),
        ]
        cursor.executemany("INSERT INTO products (name, price, stock) VALUES (?, ?, ?)", default_products)
        conn.commit()
    else:
        updated_prices = [
            (15.0, "Lenskart 1Year Discount Coupons"),
            (25.0, "Gana Plus 3Months"),
            (20.0, "Audible 2 month coupon"),
            (40.0, "Meesho ₹170 OFF JSON"),
            (60.0, "Meesho ₹195 OFF JSON"),
        ]
        for price, name in updated_prices:
            cursor.execute("UPDATE products SET price = ? WHERE name = ?", (price, name))
        conn.commit()
    conn.close()

init_db()

# ==================== KEYBOARDS ====================
def get_main_reply_keyboard():
    keyboard = [
        [KeyboardButton("🎟️ Buy Coupon"), KeyboardButton("📦 My Orders")],
        [KeyboardButton("🏷️ Enter Promo Code"), KeyboardButton("💬 Support")],
        [KeyboardButton("⚠️ Disclaimer")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== BOT HANDLERS ====================

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Start Bot Shop 🛍️")
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"✨ **WELCOME COUPON X SHOP** ✨\n\n"
        f"Hey {user.first_name}! 👋\n\n"
        f"• ⚡ Instant delivery after payment\n"
        f"• 💯 100% fresh & verified coupons\n"
        f"• 24/7 automated service\n\n"
        f"Select an option below to get started 👇"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_reply_keyboard()
    )

async def handle_text_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if "Buy Coupon" in text:
        conn = sqlite3.connect("shop_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, price, stock FROM products WHERE stock > 0")
        products = cursor.fetchall()
        conn.close()
        
        if not products:
            await update.message.reply_text("❌ Sorry, currently no items are in stock.")
            return

        keyboard = []
        for prod in products:
            p_id, name, price, stock = prod
            btn_text = f"💎 {name} | ₹{int(price)}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"buy_{p_id}")])
        
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")])
        
        await update.message.reply_text(
            "🛒 **Select Service:**\n*(Only in-stock items shown)*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    elif "My Orders" in text:
        user_id = update.effective_user.id
        conn = sqlite3.connect("shop_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT order_id, product_name, quantity, amount, status FROM orders WHERE user_id = ?", (user_id,))
        orders = cursor.fetchall()
        conn.close()
        
        if not orders:
            await update.message.reply_text("📦 You have no past orders yet.")
            return
            
        msg = "📜 **Your Orders History:**\n\n"
        for o in orders:
            msg += f"• Order #{o[0]} | {o[1]} (x{o[2]}) | ₹{o[3]} | Status: **{o[4]}**\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    elif "Enter Promo Code" in text:
        await update.message.reply_text("🏷️ Send your promo code here to redeem discounts:")
        
    elif "Support" in text:
        support_text = (
            f"📞 **Customer Support:**\n\n"
            f"If you face any issues with payment or delivery, contact admin: @{ADMIN_SUPPORT_USERNAME}"
        )
        await update.message.reply_text(support_text, parse_mode="Markdown")
        
    elif "Disclaimer" in text:
        await update.message.reply_text(
            "⚠️ **Disclaimer:**\nAll coupons and services are verified. Use them responsibly. No refunds after delivery."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "cancel_action":
        try:
            await query.message.delete()
        except:
            pass
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Action cancelled.",
            reply_markup=get_main_reply_keyboard()
        )
        return ConversationHandler.END
        
    if data.startswith("buy_"):
        p_id = int(data.split("_")[1])
        conn = sqlite3.connect("shop_data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name, price FROM products WHERE id = ?", (p_id,))
        prod = cursor.fetchone()
        conn.close()
        
        if not prod:
            try:
                await query.message.delete()
            except:
                pass
            await query.message.reply_text("❌ Product not found.")
            return
            
        name, price = prod
        context.user_data['selected_product_id'] = p_id
        context.user_data['selected_product'] = name
        context.user_data['unit_price'] = price
        
        qty_keyboard = [
            [
                InlineKeyboardButton("1", callback_data=f"qty_{p_id}_1"),
                InlineKeyboardButton("2", callback_data=f"qty_{p_id}_2"),
                InlineKeyboardButton("5", callback_data=f"qty_{p_id}_5"),
                InlineKeyboardButton("10", callback_data=f"qty_{p_id}_10"),
            ],
            [InlineKeyboardButton("✏️ Custom Quantity", callback_data=f"customqty_{p_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_action")]
        ]
        
        try:
            await query.message.edit_text(
                f"✨ **{name}** | ₹{int(price)}\n\nSelect Quantity 👇",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(qty_keyboard)
            )
        except:
            await query.message.reply_text(
                f"✨ **{name}** | ₹{int(price)}\n\nSelect Quantity 👇",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(qty_keyboard)
            )
        return

    if data.startswith("customqty_"):
        await query.message.reply_text("✏️ Please type and send the quantity you want to purchase (e.g. 3, 4, etc.):")
        return AwaitingCustomQuantity

    if data.startswith("qty_"):
        parts = data.split("_")
        p_id = int(parts[1])
        qty = int(parts[2])
        
        name = context.user_data.get('selected_product', 'Coupon')
        unit_price = context.user_data.get('unit_price', 0)
        total_amount = unit_price * qty
        
        context.user_data['selected_quantity'] = qty
        context.user_data['selected_price'] = total_amount
        
        pay_text = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"   💳 **SECURE PAYMENT GATEWAY**   \n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 **Item:** {name}\n"
            f"🔢 **Quantity:** {qty}\n"
            f"💵 **Total Payable:** `₹{total_amount}`\n\n"
            f"📲 **UPI ID (Tap to copy):**\n"
            f"`{DEFAULT_UPI_ID}`\n\n"
            f"⚡ *Scan the QR code above or pay via UPI ID, then send your payment screenshot below.*"
        )
        
        pay_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel Payment", callback_data="cancel_action")]
        ])
        
        try:
            await query.message.delete()
        except:
            pass

        if os.path.exists(CUSTOM_QR_PATH):
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=open(CUSTOM_QR_PATH, 'rb'),
                caption=pay_text,
                parse_mode="Markdown",
                reply_markup=pay_keyboard
            )
        else:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=pay_text,
                parse_mode="Markdown",
                reply_markup=pay_keyboard
            )
            
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="📸 Please send your payment screenshot now:"
        )
        return AwaitingPaymentScreenshot

    if data.startswith("admin_gen_"):
        order_id = int(data.split("_")[2])
        context.user_data['pending_order_id'] = order_id
        await query.message.reply_text("✍️ Please enter your key or link in chat:")
        return AwaitingCustomKeyInput

    if data.startswith("admin_rej_"):
        order_id = int(data.split("_")[2])
        conn = sqlite3.connect("shop_data.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status = 'Rejected' WHERE order_id = ?", (order_id,))
        cursor.execute("SELECT user_id FROM orders WHERE order_id = ?", (order_id,))
        res = cursor.fetchone()
        conn.commit()
        conn.close()
        
        if res:
            await context.bot.send_message(chat_id=res[0], text="❌ Your payment/order has been rejected by admin.")
        
        try:
            await query.message.delete()
        except:
            pass
        await query.message.reply_text(f"❌ Order #{order_id} has been Rejected.")
        return ConversationHandler.END

async def receive_custom_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip())
        if qty <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ Invalid quantity. Please enter a valid number (e.g., 3):")
        return AwaitingCustomQuantity
        
    name = context.user_data.get('selected_product', 'Coupon')
    unit_price = context.user_data.get('unit_price', 0)
    total_amount = unit_price * qty
    
    context.user_data['selected_quantity'] = qty
    context.user_data['selected_price'] = total_amount
    
    pay_text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"   💳 **SECURE PAYMENT GATEWAY**   \n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 **Item:** {name}\n"
        f"🔢 **Quantity:** {qty}\n"
        f"💵 **Total Payable:** `₹{total_amount}`\n\n"
        f"📲 **UPI ID (Tap to copy):**\n"
        f"`{DEFAULT_UPI_ID}`\n\n"
        f"⚡ *Scan the QR code above or pay via UPI ID, then send your payment screenshot below.*"
    )
    
    pay_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Payment", callback_data="cancel_action")]
    ])
    
    if os.path.exists(CUSTOM_QR_PATH):
        await update.message.reply_photo(
            photo=open(CUSTOM_QR_PATH, 'rb'),
            caption=pay_text,
            parse_mode="Markdown",
            reply_markup=pay_keyboard
        )
    else:
        await update.message.reply_text(pay_text, parse_mode="Markdown", reply_markup=pay_keyboard)
        
    await update.message.reply_text("📸 Please send your payment screenshot now:")
    return AwaitingPaymentScreenshot

async def receive_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]
    
    product_name = context.user_data.get('selected_product', 'Custom Item')
    quantity = context.user_data.get('selected_quantity', 1)
    amount = context.user_data.get('selected_price', 0)
    
    conn = sqlite3.connect("shop_data.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (user_id, username, product_name, quantity, amount, status) VALUES (?, ?, ?, ?, ?, ?)",
        (user.id, user.username or user.first_name, product_name, quantity, amount, "Pending")
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    admin_caption = (
        f"🚨 New Order #{order_id} Received!\n\n"
        f"👤 User: {user.first_name} (@{user.username or 'No Username'})\n"
        f"🆔 User ID: {user.id}\n"
        f"📦 Product: {product_name}\n"
        f"🔢 Quantity: {quantity}\n"
        f"💰 Total Amount: ₹{amount}"
    )
    
    admin_keyboard = [
        [
            InlineKeyboardButton("🟢 Approve & Send Key", callback_data=f"admin_gen_{order_id}"),
            InlineKeyboardButton("🔴 Reject Order", callback_data=f"admin_rej_{order_id}")
        ]
    ]
    
    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo.file_id,
        caption=admin_caption,
        reply_markup=InlineKeyboardMarkup(admin_keyboard)
    )
    
    await update.message.reply_text("✅ Payment screenshot submitted successfully! Admin will verify and send your key soon.")
    return ConversationHandler.END

async def receive_admin_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_input = update.message.text.strip()
    order_id = context.user_data.get('pending_order_id')
    
    if not order_id:
        await update.message.reply_text("❌ Error: Order ID not found.")
        return ConversationHandler.END
        
    conn = sqlite3.connect("shop_data.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'Completed' WHERE order_id = ?", (order_id,))
    cursor.execute("SELECT user_id, product_name, quantity FROM orders WHERE order_id = ?", (order_id,))
    order_data = cursor.fetchone()
    conn.commit()
    conn.close()
    
    if order_data:
        user_id, product_name, quantity = order_data
        
        # FIXED: Plain text formatting so multiple links/keys appear naturally in message body with active preview
        if admin_input.startswith("http://") or admin_input.startswith("https://"):
            delivery_msg = (
                f"🎉 Your Order #{order_id} is Successfully Approved!\n\n"
                f"📦 Product: {product_name} (x{quantity})\n"
                f"🔗 Your Link / Key:\n{admin_input}\n\n"
                f"Thank you for shopping with us! ✨"
            )
        else:
            delivery_msg = (
                f"🎉 Your Order #{order_id} is Successfully Approved!\n\n"
                f"📦 Product: {product_name} (x{quantity})\n"
                f"🔑 Your Key / Details:\n{admin_input}\n\n"
                f"Thank you for shopping with us! ✨"
            )

        await context.bot.send_message(
            chat_id=user_id, 
            text=delivery_msg,
            disable_web_page_preview=False
        )
        await update.message.reply_text(f"✅ Successfully sent to customer for Order #{order_id}!")
    else:
        await update.message.reply_text("❌ Order record missing in database.")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=get_main_reply_keyboard())
    return ConversationHandler.END

# ==================== MAIN SETUP ====================
def main():
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_callback, pattern="^(buy_|admin_gen_)"),
            MessageHandler(filters.PHOTO, receive_screenshot)
        ],
        states={
            AwaitingPaymentScreenshot: [
                MessageHandler(filters.PHOTO, receive_screenshot),
                CallbackQueryHandler(button_callback)
            ],
            AwaitingCustomQuantity: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_quantity)
            ],
            AwaitingCustomKeyInput: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_key)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_menu))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot is up and running...")
    app.run_polling()

if __name__ == "__main__":
    main()