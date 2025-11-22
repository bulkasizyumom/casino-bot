import asyncio
import time
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.types import ContentType

from libraries.users import Users

# Настраиваем логгер
logger = logging.getLogger(__name__)

class MessagesHandler:
    def __init__(self, dp: Dispatcher, bot: Bot, games: dict, database: Users):
        self.register(dp, bot, games, database)
        self.last_dice_time = {}  # Словарь для хранения времени последнего депа по пользователям
    
    def register(self, dp, bot, games: dict, database: Users):
        async def process_dice(message: types.Message, emoji: str, value: int, user: int):
            # 🔥 РЕГИСТРИРУЕМ ПОЛЬЗОВАТЕЛЯ ЕСЛИ ЕГО НЕТ
            if not database.get('users', user):
                database.add(user, message.from_user.full_name)

            # Проверяем, что сообщение не переслано
            if message.forward_date:
                return  # Игнорируем пересланные сообщения

            # Проверяем анти-спам защиту (минимум 0.3 секунды между депами)
            current_time = time.time()
            user_key = f"{user}_{message.chat.id}"
            
            if user_key in self.last_dice_time:
                time_diff = current_time - self.last_dice_time[user_key]
                if time_diff < 0.3:  # Меньше 0.3 секунды
                    # 🔥 ЛОГИРУЕМ АНТИ-СПАМ
                    logger.warning(
                        f"🚫 АНТИ-СПАМ: "
                        f"UserID={user}, "
                        f"Name={message.from_user.full_name}, "
                        f"TimeDiff={time_diff:.3f}s"
                    )
                    return  # Игнорируем слишком частые депы
            
            # Обновляем время последнего депа
            self.last_dice_time[user_key] = current_time

            # ... остальной код БЕЗ ИЗМЕНЕНИЙ ...

        @dp.message_handler(commands=['dice', 'slots', 'bask', 'dart', 'foot', 'bowl'])
        async def roll_dice(message: types.Message):
            # Проверяем анти-спам защиту для команд
            current_time = time.time()
            user_key = f"{message.from_user.id}_{message.chat.id}"
            
            if user_key in self.last_dice_time:
                time_diff = current_time - self.last_dice_time[user_key]
                if time_diff < 0.3:  # Меньше 0.3 секунды
                    # 🔥 ЛОГИРУЕМ АНТИ-СПАМ ДЛЯ КОМАНД
                    logger.warning(
                        f"🚫 АНТИ-СПАМ КОМАНДА: "
                        f"UserID={message.from_user.id}, "
                        f"Name={message.from_user.full_name}, "
                        f"TimeDiff={time_diff:.3f}s"
                    )
                    await message.reply("⏳ <b>Слишком быстро!</b> Подождите немного перед следующим броском.")
                    return
            
            # Обновляем время последнего депа
            self.last_dice_time[user_key] = current_time

            # ... остальной код БЕЗ ИЗМЕНЕНИЙ ...

