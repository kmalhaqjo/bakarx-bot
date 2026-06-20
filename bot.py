#!/usr/bin/env python3
"""
BakarX Telegram Bot
صرافی بکر - سیستم مدیریت حواله و USDT
"""

import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ═══════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════
BOT_TOKEN  = os.getenv("BOT_TOKEN", "8631247824:AAGxQxMLvV3JMNWfJofsIsEtAh6W2X049p0")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1004437820092"))
OWNER_ID   = int(os.getenv("OWNER_ID", "909200283"))

DATA_FILE  = "bakarx_data.json"

# ═══════════════════════════════════════════
# DATA STORE
# ═══════════════════════════════════════════
store = {
    "admins": {},
    "rates": {"sar_buy": 3.82, "sar_sell": 3.90, "usd_afn": 71.5},
    "balances": {"usdt": 0.0, "usd": 0.0, "sar": 0.0},
    "remittances": [],
    "usdt_trades": [],
    "next_id": 1,
    "next_uid": 1,
}

def save_store():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)

def load_store():
    global store
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            store.update(data)

def now_str():
    return datetime.now().strftime("%d/%m %H:%M")

def date_str():
    return datetime.now().strftime("%d/%m/%Y")

# ═══════════════════════════════════════════
# ACCESS CONTROL
# ═══════════════════════════════════════════
def is_owner(uid):
    return uid == OWNER_ID

def is_admin(uid):
    return uid == OWNER_ID or str(uid) in store["admins"]

def can_edit(uid):
    if uid == OWNER_ID:
        return True
    u = store["admins"].get(str(uid))
    return u is not None and u.get("role") == "admin"

def get_user_info(uid):
    if uid == OWNER_ID:
        return {"name": "مالک", "city": "مرکز", "role": "owner"}
    return store["admins"].get(str(uid), {"name": "نامشخص", "city": "—", "role": "admin"})

# ═══════════════════════════════════════════
# FORMATTERS
# ═══════════════════════════════════════════
def fmt_remittance(r):
    status_map = {"pending": "⏳ در انتظار اجرا", "done": "✅ اجرا شد", "problem": "⚠️ مشکل دارد"}
    return (
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🧾 حواله #{r['id']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 فرستنده : {r['sender']}\n"
        f"👤 گیرنده  : {r['receiver']}\n"
        f"📞 تماس    : {r.get('phone', '—')}\n"
        f"💰 مبلغ    : {r['amount']:,} {r['currency']}\n"
        f"📍 مقصد    : {r['dest']}\n"
        f"🏦 صرافی   : {r['partner']}\n"
        f"👨‍💼 ثبت کننده: {r.get('registered_by', '—')}\n"
        f"⏰ زمان    : {r['time']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"{status_map.get(r['status'], '⏳')}"
    )

def fmt_usdt(t):
    type_label = "🟢 خرید USDT" if t['type'] == "buy" else "📤 ارسال USDT"
    detail = f"💵 پرداخت: {t.get('sar', 0):,} SR" if t['type'] == "buy" else f"💵 معادل: ${t.get('usd', 0):,}"
    return (
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💎 {type_label} #{t['id']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {'از' if t['type'] == 'buy' else 'به'} : {t['person']}\n"
        f"🪙 مقدار  : {t['amount']} USDT\n"
        f"💱 نرخ    : {t['rate']} SR\n"
        f"{detail}\n"
        f"📡 شبکه   : {t.get('network', 'TRC20')}\n"
        f"⏰ زمان   : {t['time']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ در انتظار تأیید"
    )

def fmt_balance():
    b = store["balances"]
    r = store["rates"]
    return (
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏦 وضعیت موجودی BakarX\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💎 USDT  : {b['usdt']:,.2f}\n"
        f"💵 دالر  : ${b['usd']:,.2f}\n"
        f"🇸🇦 ریال : {b['sar']:,.2f} SR\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💱 نرخ امروز:\n"
        f"  خرید  : {r['sar_buy']} SR\n"
        f"  فروش  : {r['sar_sell']} SR\n"
        f"  AFN   : {r['usd_afn']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📅 {now_str()}"
    )

def fmt_report():
    today = date_str()
    remits = [r for r in store["remittances"] if today in r.get('time', '')]
    usdt_buys = [t for t in store["usdt_trades"] if t['type'] == 'buy' and today in t.get('time', '')]
    total_usdt = sum(t['amount'] for t in usdt_buys)
    pending = [r for r in store["remittances"] if r['status'] == 'pending']
    done = [r for r in remits if r['status'] == 'done']
    profit = sum(t['amount'] * (store['rates']['sar_sell'] - store['rates']['sar_buy']) for t in usdt_buys)
    return (
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📊 گزارش روز | {today}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🧾 حواله امروز   : {len(remits)}\n"
        f"✅ تکمیل شده    : {len(done)}\n"
        f"⏳ در انتظار    : {len(pending)}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💎 USDT خرید    : {total_usdt:,.2f}\n"
        f"📈 سود تقریبی   : ${profit:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💎 موجودی USDT  : {store['balances']['usdt']:,.2f}\n"
        f"💵 موجودی USD   : ${store['balances']['usd']:,.2f}\n"
        f"🇸🇦 موجودی SAR  : {store['balances']['sar']:,.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✅ روز خوبی داشتید 🤲"
    )

# ═══════════════════════════════════════════
# MAIN MENU
# ═══════════════════════════════════════════
def get_main_menu(uid):
    keyboard = []
    if can_edit(uid):
        keyboard.append([
            InlineKeyboardButton("🧾 حواله جدید", callback_data="new_remit"),
            InlineKeyboardButton("💎 USDT جدید", callback_data="new_usdt"),
        ])
    keyboard.append([
        InlineKeyboardButton("🏦 موجودی", callback_data="balance"),
        InlineKeyboardButton("📊 گزارش امروز", callback_data="report"),
    ])
    keyboard.append([
        InlineKeyboardButton("⏳ حواله‌های باز", callback_data="pending"),
    ])
    if can_edit(uid):
        keyboard.append([InlineKeyboardButton("💱 تغییر نرخ", callback_data="set_rate")])
    if is_owner(uid):
        keyboard.append([InlineKeyboardButton("👥 مدیریت ادمین‌ها", callback_data="manage_admins")])
    return InlineKeyboardMarkup(keyboard)

# ═══════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("⛔ دسترسی ندارید.\nبا مالک سیستم تماس بگیرید.")
        return
    info = get_user_info(uid)
    role_text = {"owner": "مالک 👑", "admin": "ادمین ✅", "viewer": "مشاهده‌گر 👁"}.get(info.get("role", ""), "")
    await update.message.reply_text(
        f"🌟 *BakarX — صرافی بکر*\n\n"
        f"👋 خوش آمدید {info.get('name', '')}\n"
        f"🏙 شهر: {info.get('city', 'مرکز')}\n"
        f"🔑 نقش: {role_text}\n\n"
        f"📅 {now_str()}\n\nچه کاری انجام دهم؟",
        reply_markup=get_main_menu(uid),
        parse_mode="Markdown"
    )

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text(fmt_balance())

async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text(fmt_report())

async def cmd_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid): return
    pending = [r for r in store["remittances"] if r['status'] == 'pending']
    if not pending:
        await update.message.reply_text("✅ هیچ حواله باز نیست!")
        return
    for r in pending:
        keyboard = []
        if can_edit(uid):
            keyboard.append([
                InlineKeyboardButton("✅ اجرا شد", callback_data=f"confirm_{r['id']}"),
                InlineKeyboardButton("⚠️ مشکل", callback_data=f"problem_{r['id']}"),
            ])
        await update.message.reply_text(
            fmt_remittance(r),
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )

async def cmd_rate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not can_edit(uid): return
    args = ctx.args
    try:
        rates = {}
        for i in range(0, len(args)-1, 2):
            key, val = args[i], float(args[i+1])
            if key == "buy":  rates["sar_buy"] = val
            if key == "sell": rates["sar_sell"] = val
            if key == "afn":  rates["usd_afn"] = val
        store["rates"].update(rates)
        save_store()
        await update.message.reply_text(
            f"✅ نرخ‌ها ذخیره شد!\n"
            f"خرید: {store['rates']['sar_buy']} SR\n"
            f"فروش: {store['rates']['sar_sell']} SR\n"
            f"AFN: {store['rates']['usd_afn']}"
        )
    except:
        await update.message.reply_text("فرمت:\n/rate buy 3.82 sell 3.90 afn 71.5")

async def cmd_addadmin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_owner(uid):
        await update.message.reply_text("⛔ فقط مالک می‌تواند ادمین اضافه کند.")
        return
    try:
        args = ctx.args
        new_id = str(args[0])
        name = args[1]
        city = args[2]
        role = args[3] if len(args) > 3 else "admin"
        store["admins"][new_id] = {"name": name, "city": city, "role": role}
        save_store()
        await update.message.reply_text(
            f"✅ ادمین جدید اضافه شد!\n"
            f"👤 نام: {name}\n"
            f"🏙 شهر: {city}\n"
            f"🔑 نقش: {role}\n"
            f"🆔 ID: {new_id}"
        )
    except:
        await update.message.reply_text(
            "فرمت:\n/addadmin <id> <name> <city> <role>\n\n"
            "مثال:\n/addadmin 123456789 احمد کابل admin\n"
            "/addadmin 987654321 علی مزار viewer"
        )

async def cmd_removeadmin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_owner(uid):
        await update.message.reply_text("⛔ فقط مالک می‌تواند ادمین حذف کند.")
        return
    try:
        target_id = str(ctx.args[0])
        if target_id in store["admins"]:
            name = store["admins"][target_id]["name"]
            del store["admins"][target_id]
            save_store()
            await update.message.reply_text(f"✅ ادمین {name} حذف شد.")
        else:
            await update.message.reply_text("❌ این ID در لیست ادمین‌ها نیست.")
    except:
        await update.message.reply_text("فرمت:\n/removeadmin <id>")

async def cmd_admins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_owner(uid): return
    if not store["admins"]:
        await update.message.reply_text("هیچ ادمینی ثبت نشده.")
        return
    text = "👥 لیست ادمین‌ها:\n━━━━━━━━━━━━━━━━━━━\n"
    for aid, info in store["admins"].items():
        role_emoji = "✅" if info['role'] == 'admin' else "👁"
        text += f"{role_emoji} {info['name']} | {info['city']} | ID: {aid}\n"
    await update.message.reply_text(text)

# ═══════════════════════════════════════════
# USER STATE
# ═══════════════════════════════════════════
user_state = {}

# ═══════════════════════════════════════════
# BUTTON HANDLER
# ═══════════════════════════════════════════
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if not is_admin(uid):
        await query.edit_message_text("⛔ دسترسی ندارید.")
        return

    if data == "new_remit":
        if not can_edit(uid):
            await query.edit_message_text("⛔ شما فقط مشاهده‌گر هستید.")
            return
        user_state[uid] = {"step": "remit_sender", "data": {}}
        await query.edit_message_text("🧾 *حواله جدید*\n\n👤 نام فرستنده را بنویسید:", parse_mode="Markdown")

    elif data == "new_usdt":
        if not can_edit(uid):
            await query.edit_message_text("⛔ شما فقط مشاهده‌گر هستید.")
            return
        keyboard = [[
            InlineKeyboardButton("🟢 خرید USDT", callback_data="usdt_buy"),
            InlineKeyboardButton("📤 ارسال USDT", callback_data="usdt_send"),
        ]]
        await query.edit_message_text(
            "💎 *معامله USDT*\n\nنوع معامله را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data in ["usdt_buy", "usdt_send"]:
        utype = "buy" if data == "usdt_buy" else "send"
        user_state[uid] = {"step": "usdt_person", "data": {"type": utype}}
        label = "از چه کسی می‌خرید" if utype == "buy" else "به چه کسی می‌فرستید"
        await query.edit_message_text(f"💎 {label}؟\n\nنام را بنویسید:")

    elif data == "balance":
        await query.edit_message_text(fmt_balance())

    elif data == "report":
        await query.edit_message_text(fmt_report())

    elif data == "pending":
        pending = [r for r in store["remittances"] if r['status'] == 'pending']
        if not pending:
            await query.edit_message_text("✅ هیچ حواله باز نیست!")
        else:
            await query.edit_message_text(f"⏳ {len(pending)} حواله باز دارید.\n/pending را بزنید.")

    elif data == "set_rate":
        await query.edit_message_text(
            "💱 *تغییر نرخ*\n\nفرمت:\n`/rate buy 3.82 sell 3.90 afn 71.5`",
            parse_mode="Markdown"
        )

    elif data == "manage_admins":
        if not is_owner(uid):
            await query.edit_message_text("⛔ فقط مالک.")
            return
        count = len(store["admins"])
        await query.edit_message_text(
            f"👥 *مدیریت ادمین‌ها*\n\n"
            f"تعداد ادمین‌ها: {count}\n\n"
            f"➕ اضافه کردن ادمین:\n`/addadmin ID نام شهر admin`\n\n"
            f"👁 اضافه کردن مشاهده‌گر:\n`/addadmin ID نام شهر viewer`\n\n"
            f"➖ حذف:\n`/removeadmin ID`\n\n"
            f"📋 لیست:\n`/admins`",
            parse_mode="Markdown"
        )

    elif data.startswith("confirm_"):
        if not can_edit(uid):
            await query.edit_message_text("⛔ شما فقط مشاهده‌گر هستید.")
            return
        rid = int(data.split("_")[1])
        for r in store["remittances"]:
            if r['id'] == rid:
                r['status'] = 'done'
                save_store()
                await ctx.bot.send_message(
                    CHANNEL_ID,
                    f"✅ *حواله #{rid} اجرا شد!*\n"
                    f"👤 گیرنده: {r['receiver']}\n"
                    f"💰 مبلغ: {r['amount']:,} {r['currency']}\n"
                    f"📍 {r['dest']}\n"
                    f"⏰ {now_str()}",
                    parse_mode="Markdown"
                )
                await query.edit_message_text(f"✅ حواله #{rid} تأیید شد!")
                break

    elif data.startswith("problem_"):
        if not can_edit(uid):
            await query.edit_message_text("⛔ شما فقط مشاهده‌گر هستید.")
            return
        rid = int(data.split("_")[1])
        for r in store["remittances"]:
            if r['id'] == rid:
                r['status'] = 'problem'
                save_store()
                await query.edit_message_text(f"⚠️ حواله #{rid} مشکل‌دار ثبت شد.")
                break

# ═══════════════════════════════════════════
# CALLBACK FORM
# ═══════════════════════════════════════════
async def callback_form(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if uid not in user_state:
        return
    state = user_state[uid]
    d = state["data"]

    if data.startswith("cur_"):
        d["currency"] = data[4:]
        state["step"] = "remit_dest"
        await query.edit_message_text("📍 شهر مقصد را بنویسید:")

    elif data.startswith("par_"):
        d["partner"] = data[4:]
        await _save_remittance(query, ctx, uid, d)

    elif data.startswith("net_"):
        d["network"] = data[4:]
        state["step"] = "usdt_txid"
        await query.edit_message_text("🔗 TXID تراکنش را بنویسید (یا — بنویسید):")

# ═══════════════════════════════════════════
# MESSAGE HANDLER
# ═══════════════════════════════════════════
async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    text = update.message.text.strip()

    if uid not in user_state:
        await update.message.reply_text("برای شروع /start را بزنید.")
        return

    state = user_state[uid]
    step = state["step"]
    d = state["data"]

    if step == "remit_sender":
        d["sender"] = text
        state["step"] = "remit_receiver"
        await update.message.reply_text("👤 نام گیرنده را بنویسید:")

    elif step == "remit_receiver":
        d["receiver"] = text
        state["step"] = "remit_phone"
        await update.message.reply_text("📞 شماره تماس گیرنده (یا — بنویسید):")

    elif step == "remit_phone":
        d["phone"] = text
        state["step"] = "remit_amount"
        await update.message.reply_text("💰 مبلغ را بنویسید (فقط عدد):")

    elif step == "remit_amount":
        try:
            d["amount"] = float(text.replace(",", ""))
            state["step"] = "remit_currency"
            keyboard = [[
                InlineKeyboardButton("🇦🇫 AFN", callback_data="cur_AFN"),
                InlineKeyboardButton("💵 USD", callback_data="cur_USD"),
                InlineKeyboardButton("🇸🇦 SAR", callback_data="cur_SAR"),
            ]]
            await update.message.reply_text("💱 ارز را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await update.message.reply_text("⚠️ فقط عدد بنویسید. دوباره:")

    elif step == "remit_dest":
        d["dest"] = text
        state["step"] = "remit_partner"
        keyboard = [[
            InlineKeyboardButton("حمیدی", callback_data="par_حمیدی"),
            InlineKeyboardButton("احمد نیازی", callback_data="par_احمد نیازی"),
            InlineKeyboardButton("جبار خان", callback_data="par_جبار خان"),
        ]]
        await update.message.reply_text("🏦 کدام صرافی اجرا کند؟", reply_markup=InlineKeyboardMarkup(keyboard))

    elif step == "usdt_person":
        d["person"] = text
        state["step"] = "usdt_amount"
        await update.message.reply_text("💎 مقدار USDT (فقط عدد):")

    elif step == "usdt_amount":
        try:
            d["amount"] = float(text.replace(",", ""))
            state["step"] = "usdt_rate"
            await update.message.reply_text(
                f"💱 نرخ SAR:\n(نرخ فعلی خرید: {store['rates']['sar_buy']})\nعدد را بنویسید:"
            )
        except:
            await update.message.reply_text("⚠️ فقط عدد. دوباره:")

    elif step == "usdt_rate":
        try:
            d["rate"] = float(text)
            state["step"] = "usdt_network"
            keyboard = [[
                InlineKeyboardButton("TRC20", callback_data="net_TRC20"),
                InlineKeyboardButton("BEP20", callback_data="net_BEP20"),
                InlineKeyboardButton("ERC20", callback_data="net_ERC20"),
            ]]
            await update.message.reply_text("📡 شبکه انتقال:", reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await update.message.reply_text("⚠️ فقط عدد. دوباره:")

    elif step == "usdt_txid":
        d["txid"] = text
        await _save_usdt(update, ctx, uid, d)

# ═══════════════════════════════════════════
# SAVE FUNCTIONS
# ═══════════════════════════════════════════
async def _save_remittance(query, ctx, uid, d):
    rid = store["next_id"]
    store["next_id"] += 1
    info = get_user_info(uid)
    r = {
        "id": rid,
        "sender": d["sender"],
        "receiver": d["receiver"],
        "phone": d.get("phone", "—"),
        "amount": d["amount"],
        "currency": d["currency"],
        "dest": d["dest"],
        "partner": d["partner"],
        "registered_by": info.get("name", "—"),
        "status": "pending",
        "time": now_str(),
    }
    store["remittances"].insert(0, r)
    save_store()
    del user_state[uid]

    await query.edit_message_text(f"✅ حواله #{rid} ثبت شد!\nدر حال نشر در کانال...")

    keyboard = [[
        InlineKeyboardButton("✅ اجرا شد", callback_data=f"confirm_{rid}"),
        InlineKeyboardButton("⚠️ مشکل", callback_data=f"problem_{rid}"),
    ]]
    await ctx.bot.send_message(
        CHANNEL_ID,
        fmt_remittance(r),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def _save_usdt(update, ctx, uid, d):
    tid = f"U-{store['next_uid']}"
    store["next_uid"] += 1
    t = {
        "id": tid,
        "type": d["type"],
        "person": d["person"],
        "amount": d["amount"],
        "rate": d["rate"],
        "sar": d["amount"] * d["rate"] if d["type"] == "buy" else 0,
        "usd": d["amount"] if d["type"] == "send" else 0,
        "network": d.get("network", "TRC20"),
        "txid": d.get("txid", "—"),
        "time": now_str(),
        "status": "pending",
    }
    store["usdt_trades"].insert(0, t)

    if d["type"] == "buy":
        store["balances"]["usdt"] += d["amount"]
        store["balances"]["sar"] -= d["amount"] * d["rate"]
    else:
        store["balances"]["usdt"] -= d["amount"]

    save_store()
    del user_state[uid]

    await update.message.reply_text(
        f"✅ معامله {tid} ثبت شد!\n"
        f"{'خرید' if d['type'] == 'buy' else 'ارسال'}: {d['amount']} USDT\n"
        f"موجودی USDT: {store['balances']['usdt']:,.2f}"
    )
    await ctx.bot.send_message(CHANNEL_ID, fmt_usdt(t))

# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
def main():
    load_store()
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("report", cmd_report))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("rate", cmd_rate))
    app.add_handler(CommandHandler("addadmin", cmd_addadmin))
    app.add_handler(CommandHandler("removeadmin", cmd_removeadmin))
    app.add_handler(CommandHandler("admins", cmd_admins))

    app.add_handler(CallbackQueryHandler(callback_form, pattern="^(cur_|par_|net_)"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    print("🚀 BakarX Bot شروع به کار کرد!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
