import asyncio
import time

from aiogram import Bot, Dispatcher, types
from aiogram.types import ContentType

from libraries.users import Users

class MessagesHandler:
    def __init__(self, dp: Dispatcher, bot: Bot, games: dict, database: Users):
        self.register(dp, bot, games, database)
        self.last_dice_time = {}  # Словарь для хранения времени последнего депа по пользователям
    
    def register(self, dp, bot, games: dict, database: Users):
        async def process_dice(message: types.Message, emoji: str, value: int, user: int):
            # Проверяем, что сообщение не переслано
            if message.forward_date:
                return  # Игнорируем пересланные сообщения

            # Проверяем анти-спам защиту (минимум 0.3 секунды между депами)
            current_time = time.time()
            user_key = f"{user}_{message.chat.id}"
            
            if user_key in self.last_dice_time:
                time_diff = current_time - self.last_dice_time[user_key]
                if time_diff < 0.3:  # Меньше 0.3 секунды
                    print(f"Anti-spam: User {user} sent dice too fast ({time_diff:.3f}s)")
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
                if time_diff < 0.3:  # Меньше 0.3 секунды
                    print(f"Anti-spam: User {message.from_user.id} used command too fast ({time_diff:.3f}s)")
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


