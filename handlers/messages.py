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
        self.special_user_losing_streaks = {}  # Счетчик проигрышных депов для специального пользователя
    
    def register(self, dp, bot, games: dict, database: Users):
        # 🔥 СПЕЦИАЛЬНЫЙ ПОЛЬЗОВАТЕЛЬ
        SPECIAL_USER_ID = 751379478  # ID пользователя для специальных сообщений
        
        # 🔥 ОСНОВНОЙ ХЕНДЛЕР ДЛЯ DICE С ПРОВЕРКОЙ НА БЛОКИРОВКУ
        @dp.message_handler(content_types=ContentType.DICE)
        async def handle_dice_with_block(message: types.Message):
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            # 🔥 ПРОВЕРЯЕМ РУЧНУЮ БЛОКИРОВКУ
            if database.is_user_blocked(user_id, chat_id):
                block_info = database.get_block_info(user_id, chat_id)
                if block_info:
                    from datetime import datetime
                    end_time = datetime.strptime(block_info['end'], '%Y-%m-%d %H:%M:%S')
                    remaining = end_time - datetime.now()
                    minutes_left = int(remaining.total_seconds() / 60)
                    
                    # УПРОЩЕННОЕ СООБЩЕНИЕ О БЛОКИРОВКЕ
                    warning_msg = await bot.send_message(
                        chat_id,
                        f'🚫 Пользователь @{message.from_user.username if message.from_user.username else message.from_user.full_name} заблокирован!\n'
                        f'⏳ <b>Разблокировка через:</b> {minutes_left} минут',
                        message_thread_id=message.message_thread_id
                    )
                    
                    # Удаляем оригинальное сообщение
                    try:
                        await message.delete()
                        logger.info(f"✅ Удален dice от заблокированного пользователя {user_id}")
                    except Exception as e:
                        logger.error(f"❌ Не удалось удалить dice: {e}")
                    
                    # Удаляем предупреждение через 5 секунд
                    await asyncio.sleep(5)
                    try:
                        await warning_msg.delete()
                    except:
                        pass
                return  # Полностью прекращаем обработку
            
            # Проверяем быстрые депы (только игнорирование, без блокировки)
            current_time = time.time()
            user_key = f"{user_id}_{chat_id}"
            
            # Проверяем быстрые депы (быстрее 0.3 секунды)
            if user_key in self.last_dice_time:
                time_diff = current_time - self.last_dice_time[user_key]
                
                if time_diff < 0.3:  # Слишком быстро
                    logger.warning(
                        f"⏰ СЛИШКОМ БЫСТРО: UserID={user_id}, "
                        f"Name={message.from_user.full_name}, "
                        f"TimeDiff={time_diff:.3f}s"
                    )
                    
                    # Просто игнорируем этот деп (не засчитываем в статистике)
                    await asyncio.sleep(0.5)
                    return  # Игнорируем этот деп
            
            # Обновляем время последнего депа
            self.last_dice_time[user_key] = current_time
            
            # Проверяем обычные условия
            if message.forward_date:
                return  # Игнорируем пересланные dice

            if message.dice and message.dice.emoji in games:
                await process_dice(message, message.dice.emoji, message.dice.value, message.from_user.id)
            else:
                await message.reply(f'Неизвестный тип эмодзи: {message.dice.emoji if message.dice else "Нет эмодзи"}')

        # 🔥 ХЕНДЛЕР ДЛЯ ВСЕХ СООБЩЕНИЙ С ПРОВЕРКОЙ БЛОКИРОВКИ
        @dp.message_handler(content_types=[ContentType.TEXT, ContentType.STICKER, ContentType.ANIMATION])
        async def handle_all_messages_with_block(message: types.Message):
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            # Проверяем ручную блокировку
            if database.is_user_blocked(user_id, chat_id):
                # Отправляем сообщение только для команд /start, /casino
                if message.text and message.text.lower() in ['/start', '/casino']:
                    block_info = database.get_block_info(user_id, chat_id)
                    if block_info:
                        from datetime import datetime
                        end_time = datetime.strptime(block_info['end'], '%Y-%m-%d %H:%M:%S')
                        remaining = end_time - datetime.now()
                        minutes_left = int(remaining.total_seconds() / 60)
                        
                        warning_msg = await bot.send_message(
                            chat_id,
                            f'🚫 Пользователь @{message.from_user.username if message.from_user.username else message.from_user.full_name} заблокирован!\n'
                            f'⏳ <b>Разблокировка через:</b> {minutes_left} минут',
                            message_thread_id=message.message_thread_id
                        )
                        
                        await asyncio.sleep(5)
                        try:
                            await warning_msg.delete()
                        except:
                            pass
                
                # Удаляем сообщение от заблокированного пользователя
                try:
                    await message.delete()
                    logger.info(f"✅ Удалено сообщение от заблокированного пользователя {user_id}")
                except Exception as e:
                    logger.error(f"❌ Не удалось удалить сообщение: {e}")
                return

        async def process_dice(message: types.Message, emoji: str, value: int, user: int):
            # 🔥 РЕГИСТРИРУЕМ ПОЛЬЗОВАТЕЛЯ ЕСЛИ ЕГО НЕТ
            if not database.get('users', user):
                database.add(user, message.from_user.full_name)

            # Проверяем, что сообщение не переслано
            if message.forward_date:
                return  # Игнорируем пересланные сообщения

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

            # 🔥 СПЕЦИАЛЬНОЕ СООБЩЕНИЕ ДЛЯ ПОЛЬЗОВАТЕЛЯ 751379478
            SPECIAL_USER_ID = 751379478
            if user == SPECIAL_USER_ID:
                # Инициализируем или обновляем счетчик проигрышных депов
                user_key = f"{user}_{chat_id}"
                
                if is_win:
                    # При выигрыше сбрасываем счетчик
                    if user_key in self.special_user_losing_streaks:
                        self.special_user_losing_streaks[user_key] = 0
                else:
                    # При проигрыше увеличиваем счетчик
                    if user_key not in self.special_user_losing_streaks:
                        self.special_user_losing_streaks[user_key] = 1
                    else:
                        self.special_user_losing_streaks[user_key] += 1
                    
                    # Если 15 проигрышных депов подряд
                    if self.special_user_losing_streaks[user_key] == 15:
                        await asyncio.sleep(1)
                        special_message = await bot.send_message(
                            message.chat.id,
                            "Не грусти, пупсик, в следующий раз получится💋",
                            message_thread_id=message.message_thread_id
                        )
                        
                        # После отправки сообщения сбрасываем счетчик
                        self.special_user_losing_streaks[user_key] = 0
                        
                        # Удаляем сообщение через 10 секунд
                        await asyncio.sleep(10)
                        try:
                            await special_message.delete()
                        except:
                            pass

            # Обновляем периодическую статистику
            database.increment_period_stats(user, chat_id, game_name, tries, wins, jackpots)

            # Поздравляем если это был выигрыш и включены уведомления
            if is_win and database.get('users', user).get('congratulate'):
                await congratulate()

        @dp.message_handler(commands=['dice', 'slots', 'bask', 'dart', 'foot', 'bowl'])
        async def roll_dice(message: types.Message):
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            # Проверяем ручную блокировку
            if database.is_user_blocked(user_id, chat_id):
                block_info = database.get_block_info(user_id, chat_id)
                if block_info:
                    from datetime import datetime
                    end_time = datetime.strptime(block_info['end'], '%Y-%m-%d %H:%M:%S')
                    remaining = end_time - datetime.now()
                    minutes_left = int(remaining.total_seconds() / 60)
                    
                    warning_msg = await message.reply(
                        f'🚫 Вы заблокированы!\n'
                        f'⏳ <b>Разблокировка через:</b> {minutes_left} минут',
                        disable_notification=True
                    )
                    
                    await asyncio.sleep(5)
                    try:
                        await warning_msg.delete()
                    except:
                        pass
                return

            # Проверяем анти-спам защиту для команд (только игнорирование)
            current_time = time.time()
            user_key = f"{user_id}_{chat_id}"
            
            if user_key in self.last_dice_time:
                time_diff = current_time - self.last_dice_time[user_key]
                
                if time_diff < 0.3:
                    await message.reply(
                        "⏳ <b>Слишком быстро!</b> Подождите немного перед следующим броском.\n"
                        "<i>Этот бросок не будет засчитан в рейтингах.</i>",
                        disable_notification=True
                    )
                    return  # Игнорируем этот деп
            
            # Обновляем время последнего депа
            self.last_dice_time[user_key] = current_time

            command = message.text.lstrip('/')
            emoji = next((k for k, v in games.items() if v['name'] == command), None)

            if not emoji:
                await message.reply("Неверная команда.")
                return

            dice_message = await bot.send_dice(message.chat.id, emoji=emoji, message_thread_id=message.message_thread_id)
            await process_dice(dice_message, emoji, dice_message.dice.value, user_id)
