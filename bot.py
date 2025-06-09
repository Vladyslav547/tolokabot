import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, CallbackContext,
    CallbackQueryHandler, ConversationHandler
)

# Стани
CHECK_SUB, CHOOSE_ROLE, GUEST_NAME, GUEST_AGE, GUEST_CITY, GUEST_FIELD, GUEST_CONTACT = range(7)
PARTNER_COMPANY, PARTNER_FIELD, PARTNER_CITY, PARTNER_CONTACT = range(7, 11)

# Дані
import os

TOKEN = os.getenv("TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")


logging.basicConfig(level=logging.INFO)

def check_subscription(user_id):
    url = f"https://api.telegram.org/bot{TOKEN}/getChatMember?chat_id=@{CHANNEL_USERNAME}&user_id={user_id}"
    response = requests.get(url).json()
    status = response.get("result", {}).get("status")
    return status in ["member", "administrator", "creator"]

def start(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    if check_subscription(user_id):
        return ask_role(update, context)
    else:
        keyboard = [[InlineKeyboardButton("Я підписався ✅", callback_data="check_sub")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "Щоб продовжити, підпишіться на канал: https://t.me/bud_toloka\n\n"
            "Після цього натисніть кнопку нижче 👇",
            reply_markup=reply_markup
        )
        return CHECK_SUB

def check_sub(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    if check_subscription(query.from_user.id):
        return ask_role(query, context)
    else:
        query.edit_message_text("На жаль, ви ще не підписані. Спробуйте ще раз.")
        return CHECK_SUB

def ask_role(update_or_query, context: CallbackContext) -> int:
    keyboard = [
        [InlineKeyboardButton("Гість", callback_data="guest")],
        [InlineKeyboardButton("Бізнес-партнер", callback_data="partner")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = (
        "Вітаємо!\n\n"
        "З нагоди річниці нашого каналу, ми готуємо подію для тих, хто прагне розвиватись у будівельній сфері.\n\n"
        "Бажаєте дізнатися більше та отримати запрошення?\n\n"
        "Заповніть коротку анкету нижче👇"
    )
    if isinstance(update_or_query, Update):
        update_or_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        update_or_query.edit_message_text(text, reply_markup=reply_markup)
    return CHOOSE_ROLE

def choose_role(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    role = query.data
    if role == "guest":
        context.user_data["role"] = "Гість"
        query.edit_message_text("Як вас звати?")
        return GUEST_NAME
    else:
        context.user_data["role"] = "Бізнес-партнер"
        query.edit_message_text("Назва компанії:")
        return PARTNER_COMPANY

# Анкета Гість
def guest_name(update: Update, context: CallbackContext) -> int:
    context.user_data["name"] = update.message.text.strip()
    update.message.reply_text("Скільки вам років?")
    return GUEST_AGE

def guest_age(update: Update, context: CallbackContext) -> int:
    context.user_data["age"] = update.message.text.strip()
    update.message.reply_text("З якого ви міста?")
    return GUEST_CITY

def guest_city(update: Update, context: CallbackContext) -> int:
    context.user_data["city"] = update.message.text.strip()
    update.message.reply_text("Яка ваша сфера діяльності?")
    return GUEST_FIELD

def guest_field(update: Update, context: CallbackContext) -> int:
    context.user_data["field"] = update.message.text.strip()
    update.message.reply_text("Ваш номер телефону для звʼязку:")
    return GUEST_CONTACT

def guest_contact(update: Update, context: CallbackContext) -> int:
    context.user_data["contact"] = update.message.text.strip()
    send_data(update, context)
    update.message.reply_text("📩 Дякуємо за ваші відповіді! Незабаром ми з вами звʼяжемось і надамо всю необхідну інформацію.")
    return ConversationHandler.END

# Анкета Бізнес-партнер
def partner_company(update: Update, context: CallbackContext) -> int:
    context.user_data["company"] = update.message.text.strip()
    update.message.reply_text("Сфера діяльності:")
    return PARTNER_FIELD

def partner_field(update: Update, context: CallbackContext) -> int:
    context.user_data["field"] = update.message.text.strip()
    update.message.reply_text("Місто в якому знаходиться компанія:")
    return PARTNER_CITY

def partner_city(update: Update, context: CallbackContext) -> int:
    context.user_data["city"] = update.message.text.strip()
    update.message.reply_text("Номер телефону для звʼязку:")
    return PARTNER_CONTACT

def partner_contact(update: Update, context: CallbackContext) -> int:
    context.user_data["contact"] = update.message.text.strip()
    send_data(update, context)
    update.message.reply_text("📩 Дякуємо за ваші відповіді! Незабаром ми з вами звʼяжемось і надамо всю необхідну інформацію.")
    return ConversationHandler.END

# Надсилання інфи адміну
import html

def send_data(update: Update, context: CallbackContext):
    data = context.user_data
    user = update.effective_user
    username = user.username
    user_fullname = user.full_name

    # Екранування для HTML, щоб уникнути помилок парсингу
    def esc(text):
        return html.escape(text, quote=False) if text else ""

    user_link = f'<a href="https://t.me/{esc(username)}">{esc(user_fullname)}</a>' if username else esc(user_fullname) + " (юзернейм відсутній)"
    user_id = user.id

    text = f"📬 <b>Нова анкета: {esc(data['role'])}</b>\n"
    text += f"👤 <b>Профіль:</b> {user_link}\n"
    text += f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
    text += f"🔗 <b>Username:</b> @{esc(username) if username else 'відсутній'}\n\n"

    if data["role"] == "Гість":
        text += (
            f"👤 Ім'я: {esc(data.get('name'))}\n"
            f"🎂 Вік: {esc(data.get('age'))}\n"
            f"🏙 Місто: {esc(data.get('city'))}\n"
            f"💼 Сфера: {esc(data.get('field'))}\n"
            f"📞 Контакт: {esc(data.get('contact'))}"
        )
    else:
        text += (
            f"🏢 Компанія: {esc(data.get('company'))}\n"
            f"💼 Сфера: {esc(data.get('field'))}\n"
            f"🏙 Місто: {esc(data.get('city'))}\n"
            f"📞 Контакт: {esc(data.get('contact'))}"
        )
    context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode='HTML')


def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Анкету скасовано.")
    return ConversationHandler.END

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHECK_SUB: [CallbackQueryHandler(check_sub, pattern='check_sub')],
            CHOOSE_ROLE: [CallbackQueryHandler(choose_role)],
            GUEST_NAME: [MessageHandler(Filters.text & ~Filters.command, guest_name)],
            GUEST_AGE: [MessageHandler(Filters.text & ~Filters.command, guest_age)],
            GUEST_CITY: [MessageHandler(Filters.text & ~Filters.command, guest_city)],
            GUEST_FIELD: [MessageHandler(Filters.text & ~Filters.command, guest_field)],
            GUEST_CONTACT: [MessageHandler(Filters.text & ~Filters.command, guest_contact)],
            PARTNER_COMPANY: [MessageHandler(Filters.text & ~Filters.command, partner_company)],
            PARTNER_FIELD: [MessageHandler(Filters.text & ~Filters.command, partner_field)],
            PARTNER_CITY: [MessageHandler(Filters.text & ~Filters.command, partner_city)],
            PARTNER_CONTACT: [MessageHandler(Filters.text & ~Filters.command, partner_contact)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True,
    )

    dp.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
