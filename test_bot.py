from datetime import datetime, timezone
from queue import Queue
import unittest
from unittest.mock import MagicMock, patch

from telegram import Bot, Chat, Message, MessageEntity, Update, User
from telegram.error import TelegramError
from telegram.ext import Dispatcher

import bot


class InvitationFlowTests(unittest.TestCase):
    USER_ID = 123456789
    ADMIN_ID = -1001234567890

    def setUp(self):
        self.settings = patch.multiple(
            bot, TOKEN="test-token", ADMIN_CHAT_ID=str(self.ADMIN_ID)
        )
        self.settings.start()
        self.addCleanup(self.settings.stop)
        self.telegram = MagicMock(spec=Bot)
        self.telegram.defaults = None
        self.telegram.username = "toloka_test_bot"
        self.telegram.id = 987654321
        self.dispatcher = Dispatcher(
            self.telegram, Queue(), workers=0, use_context=True
        )
        self.user = User(
            self.USER_ID, "Іван & партнер", False, username="test_user"
        )
        self.update_id = 0

        with patch.object(bot, "Updater") as updater_factory:
            updater = updater_factory.return_value
            updater.dispatcher = self.dispatcher
            bot.main()
            updater.start_polling.assert_called_once()
            updater.idle.assert_called_once()

    def send(self, text):
        self.update_id += 1
        entities = None
        if text.startswith("/"):
            command = text.split()[0]
            entities = [MessageEntity(MessageEntity.BOT_COMMAND, 0, len(command))]
        message = Message(
            message_id=self.update_id,
            date=datetime.now(timezone.utc),
            chat=Chat(self.USER_ID, Chat.PRIVATE),
            from_user=self.user,
            text=text,
            entities=entities,
            bot=self.telegram,
        )
        self.dispatcher.process_update(Update(self.update_id, message=message))

    def messages_for(self, chat_id):
        return [
            call.kwargs
            for call in self.telegram.send_message.call_args_list
            if call.kwargs.get("chat_id") == chat_id
        ]

    def test_start_immediately_requests_name_without_subscription_or_buttons(self):
        self.send("/start")
        messages = self.messages_for(self.USER_ID)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["text"], bot.WELCOME_TEXT)
        self.assertIsNone(messages[0].get("reply_markup"))
        self.telegram.get_chat_member.assert_not_called()
        self.assertEqual(self.messages_for(self.ADMIN_ID), [])

    def test_manual_phone_delivers_name_and_number_before_thank_you(self):
        self.send("/start")
        self.send("  Олексій <Тест>  ")
        self.assertEqual(self.messages_for(self.ADMIN_ID), [])
        self.assertEqual(self.messages_for(self.USER_ID)[-1]["text"], bot.PHONE_TEXT)
        self.assertIsNone(self.messages_for(self.USER_ID)[-1].get("reply_markup"))

        self.send("+380 (67) 123-45-67")
        admin_messages = self.messages_for(self.ADMIN_ID)
        self.assertEqual(len(admin_messages), 1)
        self.assertIn("Олексій &lt;Тест&gt;", admin_messages[0]["text"])
        self.assertIn("<code>+380671234567</code>", admin_messages[0]["text"])
        self.assertIn("Іван &amp; партнер", admin_messages[0]["text"])
        self.assertIn("https://t.me/test_user", admin_messages[0]["text"])
        self.assertEqual(admin_messages[0]["parse_mode"], "HTML")
        self.assertEqual(
            self.messages_for(self.USER_ID)[-1]["text"], bot.THANK_YOU_TEXT
        )
        self.assertEqual(self.dispatcher.user_data[self.USER_ID], {})
        destinations = [
            call.kwargs["chat_id"]
            for call in self.telegram.send_message.call_args_list
        ]
        self.assertEqual(destinations[-2:], [self.ADMIN_ID, self.USER_ID])

    def test_local_phone_and_user_without_username_are_supported(self):
        self.user = User(self.USER_ID, "Владислав", False)
        self.send("/start")
        self.send("Владислав")
        self.send("0671234567")
        text = self.messages_for(self.ADMIN_ID)[0]["text"]
        self.assertIn("<code>0671234567</code>", text)
        self.assertIn("юзернейм відсутній", text)
        self.assertNotIn("@відсутній", text)

    def test_invalid_phone_is_not_forwarded_and_can_be_corrected(self):
        self.send("/start")
        self.send("Владислав")
        for phone in ("не номер", "12345", "+380671234567abc", "+" * 12):
            with self.subTest(phone=phone):
                self.send(phone)
                self.assertEqual(self.messages_for(self.ADMIN_ID), [])
                self.assertNotEqual(
                    self.messages_for(self.USER_ID)[-1]["text"], bot.THANK_YOU_TEXT
                )
        self.send("0671234567")
        self.assertEqual(len(self.messages_for(self.ADMIN_ID)), 1)

    def test_empty_or_overlong_name_is_rejected_before_requesting_phone(self):
        self.send("/start")
        for name in ("   ", "А" * 101):
            with self.subTest(name_length=len(name)):
                self.send(name)
                self.assertNotEqual(
                    self.messages_for(self.USER_ID)[-1]["text"], bot.PHONE_TEXT
                )
        self.send("Владислав")
        self.assertEqual(self.messages_for(self.USER_ID)[-1]["text"], bot.PHONE_TEXT)

    def test_restart_replaces_previous_name(self):
        self.send("/start")
        self.send("Старе ім’я")
        self.send("/start")
        self.send("Нове ім’я")
        self.send("0671234567")
        text = self.messages_for(self.ADMIN_ID)[0]["text"]
        self.assertIn("Нове ім’я", text)
        self.assertNotIn("Старе ім’я", text)

    def test_cancel_discards_unfinished_request(self):
        self.send("/start")
        self.send("Владислав")
        self.send("/cancel")
        self.send("0671234567")
        self.assertEqual(self.messages_for(self.ADMIN_ID), [])
        self.assertEqual(self.dispatcher.user_data[self.USER_ID], {})

    def test_delivery_error_keeps_request_for_retry_without_success_confirmation(self):
        delivery_failed = True

        def send_message(**kwargs):
            if kwargs["chat_id"] == self.ADMIN_ID and delivery_failed:
                raise TelegramError("Simulated delivery failure")

        self.telegram.send_message.side_effect = send_message
        self.send("/start")
        self.send("Владислав")
        with self.assertLogs(bot.logger, level="ERROR"):
            self.send("0671234567")
        self.assertNotEqual(
            self.messages_for(self.USER_ID)[-1]["text"], bot.THANK_YOU_TEXT
        )
        self.assertEqual(
            self.dispatcher.user_data[self.USER_ID]["name"], "Владислав"
        )

        delivery_failed = False
        self.send("0671234567")
        self.assertEqual(
            self.messages_for(self.USER_ID)[-1]["text"], bot.THANK_YOU_TEXT
        )
        self.assertEqual(self.dispatcher.user_data[self.USER_ID], {})


if __name__ == "__main__":
    unittest.main()
