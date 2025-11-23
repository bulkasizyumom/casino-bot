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
        # 🔥 РАЗДЕЛЬНЫЕ СПИСКИ:
        BLOCKED_USER_IDS = [1773287874]  # ПОЛНОСТЬЮ ЗАБЛОКИРОВАННЫЕ
        SLOW_USER_IDS = []  # пользователи с ограничением 3 сек (добавь нужные ID)
        
        # 🔥 ИГРОВЫЕ ЭМОДЗИ КОТОРЫЕ БЛОКИРУЕМ
        GAME_EMOJIS = ['🎰', '🎲', '🏀', '🎯', '⚽', '🎳']  # Все игровые эмодзи
        
        # 🔥 САМЫЙ ПЕРВЫЙ ХЕНДЛЕР - БЛОКИРОВКА ВСЕХ СООБЩЕНИЙ ОТ ЗАБЛОКИРОВАННЫХ
        @dp.message_handler(lambda message: message.from_user.id in BLOCKED_USER_IDS)
        async def handle_blocked_users(message: types.Message):
            """Блокирует ВСЕ сообщения от заблокированных пользователей"""
            
            block_reason = ""
            
            # Определяем тип контента для логирования
            if message.content_type == ContentType.DICE and message.dice:
                if message.dice.emoji in GAME_EMOJIS:
                    block_reason = f"игровой эмодзи {message.dice.emoji}"
                else:
                    block_reason = f"эмодзи {message.dice.emoji}"
            elif message.content_type == ContentType.STICKER:
                block_reason = "стикер"
            elif message.content_type == ContentType.ANIMATION:
                block_reason = "GIF"
            elif message.content_type == ContentType.TEXT:
                if message.text and message.text.startswith('/'):
                    command = message.text.lstrip('/').split(' ')[0]
                    if command in ['dice', 'slots', 'bask', 'dart', 'foot', 'bowl']:
                        block_reason = f"игровая команда /{command}"
                    else:
                        block_reason = f"команда /{command}"
                else:
                    block_reason = "текстовое сообщение"
            else:
                block_reason = f"тип {message.content_type}"
            
            logger.warning(
                f"🚫 БЛОКИРОВКА: "
                f"UserID={message.from_user.id}, "
                f"Name={message.from_user.full_name}, "
                f"Тип: {block_reason}"
            )
            
            # 🔥 УДАЛЯЕМ ЛЮБОЕ СООБЩЕНИЕ ОТ ЗАБЛОКИРОВАННОГО ПОЛЬЗОВАТЕЛЯ
            try:
                await message.delete()
                logger.info(f"✅ Удалено сообщение от {message.from_user.id}, причина: {block_reason}")
            except Exception as e:
                logger.error(f"❌ Не удалось удалить сообщение: {e}")
            
            return  # Полностью прекращаем обработку

        async def process_dice(message: types.Message, emoji: str, value: int, user: int):
            # 🔥 РЕГИСТРИРУЕМ ПОЛЬЗОВАТЕЛЯ ЕСЛИ ЕГО НЕТ
            if not database.get('users', user):
                database.add(user, message.from_user.full_name)

            # Проверяем, что сообщение не переслано
            if message.forward_date:
                return  # Игнорируем пересланные сообщения

            # Проверяем анти-спам защиту
            current_time = time.time()
            user_key = f"{user}_{message.chat.id}"
            
            if user_key in self.last_dice_time:
                time_diff = current_time - self.last_dice_time[user_key]
                
                # 🔥 РАЗНЫЕ НАСТРОЙКИ ДЛЯ РАЗНЫХ ГРУПП
                if user in SLOW_USER_IDS:
                    spam_threshold = 3.0  # 3 секунды для медленных пользователей
                else:
                    spam_threshold = 0.3  # 0.3 секунды для всех остальных
                
                if time_diff < spam_threshold:
                    # 🔥 ЛОГИРУЕМ АНТИ-СПАМ
                    user_type = "МЕДЛЕННЫЙ" if user in SLOW_USER_IDS else "ОБЫЧНЫЙ"
                    logger.warning(
                        f"🚫 АНТИ-СПАМ ({user_type}): "
                        f"UserID={user}, "
                        f"Name={message.from_user.full_name}, "
                        f"TimeDiff={time_diff:.3f}s, "
                        f"Threshold={spam_threshold}s"
                    )
                    return  # Игнорируем слишком частые депы
            
            # Обновляем время последнего депа
            self.last_dice_time[user_key] = current_time

            game = games[emoji]
            game_name = game['name']
            chat_id = message.chat.id

            # Обновляем основную статистику
            database.increment('tries', user, chat_id, game_name)

            # Обновляем статистику периодов
            tries = 1
            wins = 0
            jackpots = 0

            async def congratulate():
                await asyncio.sleep(1)
                await bot.send_message(
                    message.chat.id,
                    f'🤑 <b>Выигрыш!</b> Поздравляем.',
                    message_thread_id=message.message_thread_id
                )

            is_win = False
            
            # Проверяем джекпот (только для слотов)
            if emoji == '🎰' and value == game.get('jackpot'):
                database.increment('jackpots', user, chat_id, 'slots')
                database.increment('wins', user, chat_id, 'slots')  # Учитываем джекпот как выигрыш
                wins = 1
                jackpots = 1
                is_win = True
                
            # Проверяем обычные выигрыши
            elif value in game['win']:
                database.increment('wins', user, chat_id, game_name)
                wins = 1
                is_win = True

            # 🔥 ОБНОВЛЯЕМ СЕРИИ ПОБЕД
            current_streak, max_streak = database.update_win_streak(user, chat_id, game_name, is_win)
            
            # Если установлена новая максимальная серия, уведомляем
            if is_win and current_streak > 3:  # Уведомляем только при серии от 4 побед
                streak_message = ""
                if current_streak == 4:
                    streak_message = "🔥"
                elif current_streak == 5:
                    streak_message = "🔥🔥"
                elif current_streak >= 6:
                    streak_message = "🔥🔥🔥"
                
                if streak_message:
                    await asyncio.sleep(1.5)
                    await bot.send_message(
                        message.chat.id,
                        f'{streak_message} <b>Серия побед!</b> {current_streak} подряд!',
                        message_thread_id=message.message_thread_id
                    )

            # Обновляем периодическую статистику
            database.increment_period_stats(user, chat_id, game_name, tries, wins, jackpots)

            # Поздравляем если это был выигрыш и включены уведомления
            if is_win and database.get('users', user).get('congratulate'):
                await congratulate()

        @dp.message_handler(content_types=ContentType.DICE)
        async def handle_dice(message: types.Message):
            # Проверяем, что сообщение не переслано
            if message.forward_date:
                return  # Игнорируем пересланные dice

            if message.dice and message.dice.emoji in games:
                await process_dice(message, message.dice.emoji, message.dice.value, message.from_user.id)
            else:
                await message.reply(f'Неизвестный тип эмодзи: {message.dice.emoji if message.dice else "Нет эмодзи"}')

        @dp.message_handler(commands=['dice', 'slots', 'bask', 'dart', 'foot', 'bowl'])
        async def roll_dice(message: types.Message):
            # Проверяем, что команда не из пересланного сообщения
            if message.forward_date:
                return  # Игнорируем команды из пересланных сообщений

            # Проверяем анти-спам защиту для команд
            current_time = time.time()
            user_key = f"{message.from_user.id}_{message.chat.id}"
            
            if user_key in self.last_dice_time:
                time_diff = current_time - self.last_dice_time[user_key]
                
                # 🔥 РАЗНЫЕ НАСТРОЙКИ ДЛЯ РАЗНЫХ ГРУПП
                if message.from_user.id in SLOW_USER_IDS:
                    spam_threshold = 3.0  # 3 секунды для медленных пользователей
                else:
                    spam_threshold = 0.3  # 0.3 секунды для всех остальных
                
                if time_diff < spam_threshold:
                    # 🔥 ЛОГИРУЕМ АНТИ-СПАМ ДЛЯ КОМАНД
                    user_type = "МЕДЛЕННЫЙ" if message.from_user.id in SLOW_USER_IDS else "ОБЫЧНЫЙ"
                    logger.warning(
                        f"🚫 АНТИ-СПАМ КОМАНДА ({user_type}): "
                        f"UserID={message.from_user.id}, "
                        f"Name={message.from_user.full_name}, "
                        f"TimeDiff={time_diff:.3f}s, "
                        f"Threshold={spam_threshold}s"
                    )
                    await message.reply("⏳ <b>Слишком быстро!</b> Подождите немного перед следующим броском.")
                    return
            
            # Обновляем время последнего депа
            self.last_dice_time[user_key] = current_time

            command = message.text.lstrip('/')
            emoji = next((k for k, v in games.items() if v['name'] == command), None)

            if not emoji:
                await message.reply("Неверная команда.")
                return

            dice_message = await bot.send_dice(message.chat.id, emoji=emoji, message_thread_id=message.message_thread_id)
            await process_dice(dice_message, emoji, dice_message.dice.value, message.from_user.id)
            dice_message = await bot.send_dice(message.chat.id, emoji=emoji, message_thread_id=message.message_thread_id)
            await process_dice(dice_message, emoji, dice_message.dice.value, message.from_user.id)


