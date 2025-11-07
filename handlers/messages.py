import asyncio
import time

from aiogram import Bot, Dispatcher, types
from aiogram.types import ContentType

from libraries.users import Users

class MessagesHandler:
    def __init__(self, dp: Dispatcher, bot: Bot, games: dict, database: Users):
        self.register(dp, bot, games, database)
    
    def register(self, dp, bot, games: dict, database: Users):
        async def process_dice(message: types.Message, emoji: str, value: int, user: int):
            game = games[emoji]
            game_name = game['name']
            chat_id = message.chat.id

            database.increment('tries', user, chat_id, game_name)

            async def congratulate():
                await asyncio.sleep(1)
                await bot.send_message(
                    message.chat.id,
                    f'🤑 <b>Выигрыш!</b> Поздравляем.',
                    message_thread_id=message.message_thread_id
                )

            if emoji == '🎰' and value == game.get('jackpot'):
                database.increment('jackpots', user, chat_id, 'slots')
                if database.get('users', user).get('congratulate'):
                    await congratulate()

            if value in game['win']:
                database.increment('wins', user, chat_id, game_name)
                if database.get('users', user).get('congratulate'):
                    await congratulate()

        @dp.message_handler(content_types=ContentType.DICE)
        async def handle_dice(message: types.Message):
            if message.dice and message.dice.emoji in games:
                await process_dice(message, message.dice.emoji, message.dice.value, message.from_user.id)
            else:
                await message.reply(f'Неизвестный тип эмодзи: {message.dice.emoji if message.dice else "Нет эмодзи"}')

        @dp.message_handler(commands=['dice', 'slots', 'bask', 'dart', 'foot', 'bowl'])
        async def roll_dice(message: types.Message):
            command = message.text.lstrip('/')
            emoji = next((k for k, v in games.items() if v['name'] == command), None)

            if not emoji:
                await message.reply("Неверная команда.")
                return

            dice_message = await bot.send_dice(message.chat.id, emoji=emoji, message_thread_id=message.message_thread_id)
            await process_dice(dice_message, emoji, dice_message.dice.value, message.from_user.id)