import html
import logging
import os
import re

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    CallbackContext,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)


NAME, PHONE = range(2)

TOKEN = os.getenv("TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

WELCOME_TEXT = (
    "Вітаємо! 👋\n\n"
    "Запрошуємо вас долучитися до зустрічі будівельної спільноти — "
    "майстрів, представників компаній та всіх, хто пов’язаний із будівельною сферою.\n\n"
    "Зустріч відбудеться 10 жовтня в ресторанному комплексі «Вікторія» "
    "у Київській області.\n\n"
    "Хочете отримати запрошення? Напишіть, будь ласка, ваше ім’я 👇"
)

PHONE_TEXT = (
    "Тепер введіть, будь ласка, ваш номер телефону, щоб ми могли "
    "зв’язатися з вами щодо запрошення.\n\n"
    "Наприклад: +380671234567"
)

THANK_YOU_TEXT = (
    "Дякуємо! Ми отримали ваше ім’я та номер телефону ✅\n\n"
    "Незабаром з вами зв’яжуться щодо запрошення на захід. До зустрічі!"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    update.message.reply_text(WELCOME_TEXT)
    return NAME


def receive_name(update: Update, context: CallbackContext) -> int:
    name = update.message.text.strip()
    if not name or len(name) > 100:
        update.message.reply_text("Напишіть, будь ласка, ваше ім’я (до 100 символів).")
        return NAME

    context.user_data["name"] = name
    update.message.reply_text(PHONE_TEXT)
    return PHONE


def normalize_phone(text: str):
    phone = text.strip()
    if not re.fullmatch(r"\+?[0-9][0-9\s().-]*", phone):
        return None

    digits = re.sub(r"[^0-9]", "", phone)
    if not 10 <= len(digits) <= 15:
        return None

    return ("+" if phone.startswith("+") else "") + digits


def receive_phone(update: Update, context: CallbackContext) -> int:
    phone = normalize_phone(update.message.text)
    if phone is None:
        update.message.reply_text(
            "Перевірте, будь ласка, номер телефону та введіть його ще раз.\n\n"
            "Наприклад: +380671234567 або 0671234567"
        )
        return PHONE

    context.user_data["phone"] = phone
    try:
        send_data(update, context)
    except TelegramError:
        logger.error("Не вдалося надіслати заявку адміністратору.")
        update.message.reply_text(
            "Не вдалося надіслати заявку. Спробуйте, будь ласка, ще раз — "
            "введіть номер телефону повторно."
        )
        return PHONE

    update.message.reply_text(THANK_YOU_TEXT)
    context.user_data.clear()
    return ConversationHandler.END


def send_data(update: Update, context: CallbackContext):
    data = context.user_data
    user = update.effective_user
    full_name = html.escape(user.full_name)

    if user.username:
        username = html.escape(user.username)
        user_link = f'<a href="https://t.me/{username}">{full_name}</a>'
        username_text = f"@{username}"
    else:
        user_link = full_name + " (юзернейм відсутній)"
        username_text = "відсутній"

    text = (
        "📬 <b>Нова заявка на запрошення</b>\n\n"
        f"👤 <b>Ім’я:</b> {html.escape(data['name'])}\n"
        f"📞 <b>Телефон:</b> <code>{html.escape(data['phone'])}</code>\n\n"
        f"👤 <b>Профіль:</b> {user_link}\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"🔗 <b>Username:</b> {username_text}"
    )
    context.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=text, parse_mode="HTML")


def cancel(update: Update, context: CallbackContext) -> int:
    context.user_data.clear()
    update.message.reply_text("Заявку скасовано. Щоб почати знову, натисніть /start.")
    return ConversationHandler.END


def main():
    if not TOKEN or not ADMIN_CHAT_ID:
        raise RuntimeError("Вкажіть TOKEN і ADMIN_CHAT_ID у змінних середовища.")
    try:
        admin_chat_id = int(ADMIN_CHAT_ID)
    except ValueError:
        raise RuntimeError("ADMIN_CHAT_ID має бути числовим ID чату.") from None
    if admin_chat_id == 0:
        raise RuntimeError("ADMIN_CHAT_ID має бути дійсним ID чату.")

    updater = Updater(TOKEN, use_context=True)
    conversation = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(Filters.text & ~Filters.command, receive_name)],
            PHONE: [MessageHandler(Filters.text & ~Filters.command, receive_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    updater.dispatcher.add_handler(conversation)
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
