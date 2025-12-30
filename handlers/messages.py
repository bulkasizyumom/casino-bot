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
        self.waiting_for_reason = {}  # 🔥 НОВОЕ: словарь для отслеживания пользователей, вводящих причину
        self.fast_dice_ignored = {}  # 🔥 НОВОЕ: словарь для отслеживания проигнорированных быстрых депов

    # 🔥 НОВЫЙ МЕТОД ДЛЯ ОБРАБОТКИ ПРИЧИНЫ БЛОКИРОВКИ
    def add_waiting_for_reason(self, user_id: int, chat_id: int):
        self.waiting_for_reason[(user_id, chat_id)] = True
    
    def remove_waiting_for_reason(self, user_id: int, chat_id: int):
        if (user_id, chat_id) in self.waiting_for_reason:
            del self.waiting_for_reason[(user_id, chat_id)]
    
    def is_waiting_for_reason(self, user_id: int, chat_id: int):
        return (user_id, chat_id) in self.waiting_for_reason
    
    def mark_fast_dice_ignored(self, user_id: int, chat_id: int):
        """Помечает, что быстрый деп был проигнорирован"""
        key = f"{user_id}_{chat_id}"
        self.fast_dice_ignored[key] = True
    
    def is_fast_dice_ignored(self, user_id: int, chat_id: int):
        """Проверяет, был ли проигнорирован быстрый деп"""
        key = f"{user_id}_{chat_id}"
        return key in self.fast_dice_ignored
    
    def clear_fast_dice_flag(self, user_id: int, chat_id: int):
        """Очищает флаг игнорирования быстрого депа"""
        key = f"{user_id}_{chat_id}"
        if key in self.fast_dice_ignored:
            del self.fast_dice_ignored[key]

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
            
            # 🔥 ВОЗВРАЩАЕМ ПРОВЕРКУ НА БЫСТРЫЕ ДЕПЫ
            current_time = time.time()
            user_key = f"{user_id}_{chat_id}"
            
            if user_key in self.last_dice_time:
                time_diff = current_time - self.last_dice_time[user_key]
                if time_diff < 0.3:  # Меньше 0.3 секунды
                    logger.warning(f"⚡ ИГНОРИРУЕМ СПАМ ДЕП: UserID={user_id}, TimeDiff={time_diff:.3f}s")
                    # 🔥 ИСПРАВЛЕНИЕ: не удаляем сообщение, только помечаем для игнорирования
                    self.mark_fast_dice_ignored(user_id, chat_id)
                    return  # Игнорируем слишком быстрые депы в статистике
            
            # 🔥 Если предыдущий деп был проигнорирован, очищаем флаг
            self.clear_fast_dice_flag(user_id, chat_id)
            
            self.last_dice_time[user_key] = current_time
            
            # Проверяем обычные условия
            if message.forward_date:
                return  # Игнорируем пересланные dice

            if message.dice and message.dice.emoji in games:
                await process_dice(message, message.dice.emoji, message.dice.value, message.from_user.id)
            else:
                # 🔥 ИСПРАВЛЕНИЕ: Добавляем логирование для отладки
                emoji = message.dice.emoji if message.dice else "Нет эмодзи"
                logger.warning(f"Неизвестный эмодзи: '{emoji}' (код: {ord(emoji[0]) if emoji else 'нет'})")
                await message.reply(f'Неизвестный тип эмодзи: {emoji}')

        # 🔥 ХЕНДЛЕР ДЛЯ ВСЕХ СООБЩЕНИЙ С ПРОВЕРКОЙ БЛОКИРОВКИ
        @dp.message_handler(content_types=[ContentType.TEXT, ContentType.STICKER, ContentType.ANIMATION])
        async def handle_all_messages_with_block(message: types.Message):
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            # 🔥 ПРОВЕРКА: если пользователь вводит причину для помощи
            if self.is_waiting_for_reason(user_id, chat_id):
                # Убираем пользователя из ожидания
                self.remove_waiting_for_reason(user_id, chat_id)
                
                # Получаем текст причины
                reason_text = message.text if message.text else "Причина не указана"
                
                # Отправляем заявку админу
                try:
                    # Получаем информацию о пользователе
                    user_data = database.get('users', user_id)
                    user_name = user_data.get('name', message.from_user.full_name) if user_data else message.from_user.full_name
                    username = f"@{message.from_user.username}" if message.from_user.username else "нет username"
                    
                    # Получаем информацию о блокировке
                    block_info = database.get_block_info(user_id, chat_id)
                    block_reason = block_info['reason'] if block_info else "Нарушение правил"
                    
                    # Формируем текст заявки
                    help_text = (
                        f"🚫 <b>Заявка на рассмотрение блокировки (своя причина)</b>\n"
                        f"👤 <b>Пользователь:</b> {user_name}\n"
                        f"📱 <b>Username:</b> {username}\n"
                        f"🆔 <b>ID:</b> {user_id}\n"
                        f"💬 <b>Причина блокировки:</b> {block_reason}\n"
                        f"📝 <b>Причина обжалования:</b> {reason_text}\n\n"
                        f"<i>Пользователь не согласен с блокировкой и просит рассмотреть заявку.</i>"
                    )
                    
                    # Сохраняем заявку в базу данных
                    message_id = database.add_help_message(user_id, chat_id, help_text, "Своя причина")
                    
                    # Уведомляем админов
                    for admin_id in [1773287874, 1995856157]:  # ADMIN_IDS из main.py
                        try:
                            await bot.send_message(admin_id, help_text)
                        except:
                            pass
                    
                    # Уведомляем пользователя
                    await message.reply("✅ Ваша причина отправлена администратору!")
                    
                except Exception as e:
                    logger.error(f"Ошибка при обработке причины: {e}")
                    await message.reply("❌ Произошла ошибка при отправке причины.")
                
                # Удаляем сообщение с причиной
                try:
                    await message.delete()
                except:
                    pass
                
                return  # Прекращаем дальнейшую обработку
            
            # Исключаем команду /help из блокировки
            if message.text and message.text.lower() == '/help':
                return
            
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
            # 🔥 ПРОВЕРЯЕМ, БЫЛ ЛИ ЭТОТ ДЕП ПРОИГНОРИРОВАН КАК СЛИШКОМ БЫСТРЫЙ
            if self.is_fast_dice_ignored(user, message.chat.id):
                logger.info(f"⚡ Пропускаем статистику для быстрого депа UserID={user}")
                self.clear_fast_dice_flag(user, message.chat.id)
                return  # 🔥 ВОТ ЗДЕСЬ: не обновляем статистику, но сообщение остается
            
            # 🔥 РЕГИСТРИРУЕМ ПОЛЬЗОВАТЕЛЬ ЕСЛИ ЕГО НЕТ
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

            # Обновляем периодическую статистику
            database.increment_period_stats(user, chat_id, game_name, tries, wins, jackpots)

            # Поздравляем если это был выигрыш и включены уведомления
            if is_win and database.get('users', user).get('congratulate'):
                await congratulate()

        @dp.message_handler(commands=['dice', 'slots', 'bask', 'dart', 'foot', 'bowl'])
        async def roll_dice(message: types.Message):
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            # 🔥 ПРОВЕРКА НА БЫСТРЫЕ КОМАНДЫ (аналогично депам)
            current_time = time.time()
            user_key = f"{user_id}_{chat_id}_command"
            
            if user_key in self.last_dice_time:
                time_diff = current_time - self.last_dice_time[user_key]
                if time_diff < 0.3:  # Меньше 0.3 секунды
                    logger.warning(f"⚡ ИГНОРИРУЕМ СПАМ КОМАНДУ: UserID={user_id}, TimeDiff={time_diff:.3f}s")
                    await message.reply("⏰ Слишком быстро! Подождите немного...", delete_after=3)
                    return
            
            self.last_dice_time[user_key] = current_time
            
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

            command = message.text.lstrip('/')
            emoji = next((k for k, v in games.items() if v['name'] == command), None)

            if not emoji:
                await message.reply("Неверная команда.")
                return

            dice_message = await bot.send_dice(message.chat.id, emoji=emoji, message_thread_id=message.message_thread_id)
            await process_dice(dice_message, emoji, dice_message.dice.value, user_id)

