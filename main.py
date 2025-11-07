import json, os, time, logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ContentType

from handlers.messages import MessagesHandler
from handlers.rating import RatingHandler
from libraries.users import Users
from database.database import Database

# variables

load_dotenv()

BOT = Bot(token = os.getenv('BOT_TOKEN'), parse_mode = 'HTML')
STORAGE = MemoryStorage()
DP = Dispatcher(BOT, storage=STORAGE)

DATABASE = Database('data.db')
USERS = Users(DATABASE)

GAMES = {
    '🎰': {'name': 'slots', 'win': [1, 22, 43], 'jackpot': 64},
    '🏀': {'name': 'bask',  'win': [4, 5]},
    '🎯': {'name': 'dart',  'win': [6]},
    '⚽': {'name': 'foot',  'win': [3, 5]},
    '🎳': {'name': 'bowl',  'win': [6]},
    '🎲': {'name': 'dice',  'win': [1]},
}

# Добавляем админов (замените на реальные ID)
ADMIN_IDS = [1773287874, 1995856157]  # Замените на реальные ID администраторов
for admin_id in ADMIN_IDS:
    USERS.add_admin(admin_id)

# user register

class UserRegistrationMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        if not USERS.get('users', message.from_user.id):
            USERS.add(message.from_user.id, message.from_user.full_name)

DP.middleware.setup(UserRegistrationMiddleware())

# main menu handler

@DP.message_handler(commands=['casino', 'start'])
async def main_menu(message: types.Message):
    user = message.from_user.id
    chat_id = message.chat.id

    wins = USERS.get('wins', user, chat_id) or {}
    tries = USERS.get('tries', user, chat_id) or {}
    jackpots = USERS.get('jackpots', user, chat_id) or {}

    # Безопасный подсчет с проверкой на None
    total_jackpots = sum([val for i, val in jackpots.items() if i not in ['id', 'chat_id', 'timestamp'] and val is not None])
    total_wins = sum([val for i, val in wins.items() if i not in ['id', 'chat_id', 'timestamp'] and val is not None])
    total_tries = sum([val for i, val in tries.items() if i not in ['id', 'chat_id', 'timestamp'] and val is not None])

    text = f"""🎰 <b>Здравствуйте, {f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name}!</b>
        
    ⭐ <b>Всего джекпотов</b>: {total_jackpots}
    ✔ <b>Всего выигрышей</b>: {total_wins}
    🏅 <b>Всего попыток</b>: {total_tries}

    🎮 <b>Игры</b>: /games
    📩 <b>Оповещение о выигрыше: /congratulate</b>"""

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('📊 Статистика', callback_data='stats'))
    keyboard.add(InlineKeyboardButton('🏆 Рейтинг', callback_data='rating'))
    
    # Добавляем кнопку для админов
    if USERS.is_admin(message.from_user.id):
        keyboard.add(InlineKeyboardButton('⚙️ Админ', callback_data='admin'))

    await BOT.send_message(
        message.chat.id, text,
        message_thread_id = message.message_thread_id,
        reply_markup=keyboard
    )

# games

@DP.message_handler(commands=['games'])
async def games(message: types.Message):
    text = f"""🎰 <b>Слоты:</b> /slots
🎲 <b>Кубик:</b> /dice
⚽ <b>Футбол:</b> /foot
🎳 <b>Боулинг:</b> /bowl
🏀 <b>Баскетбол:</b> /bask
🎯 <b>Дартс:</b> /dart"""

    await BOT.send_message(
        message.chat.id, text,
        message_thread_id = message.message_thread_id
    )

# statistics handler

@DP.callback_query_handler(lambda c: c.data == 'stats')
async def full_stats(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🎰", callback_data="stats-slots"), InlineKeyboardButton("🎲", callback_data="stats-dice"), InlineKeyboardButton("⚽", callback_data="stats-foot")],
        [InlineKeyboardButton("🎳", callback_data="stats-bowl"), InlineKeyboardButton("🏀", callback_data="stats-bask"), InlineKeyboardButton("🎯", callback_data="stats-dart")],
        [InlineKeyboardButton("♻️ Сбросить", callback_data="stats-reset")],
    ])

    await BOT.send_message(
        chat_id=callback.message.chat.id,
        text="📊 <b>Выберите категорию статистики:</b>",
        reply_markup=keyboard,
        message_thread_id=callback.message.message_thread_id
    )
    await callback.answer()

@DP.callback_query_handler(lambda c: c.data and c.data.startswith('stats-'))
async def handle_stats_callback(callback: types.CallbackQuery):
    user = callback.from_user.id
    chat_id = callback.message.chat.id
    category = callback.data.split('-')[1]

    wins = USERS.get('wins', user, chat_id) or {}
    tries = USERS.get('tries', user, chat_id) or {}
    jackpots = USERS.get('jackpots', user, chat_id) or {}

    if category == "slots":
        text = f"""🎰 <b>СТАТИСТИКА СЛОТОВ</b>
        Джекпоты: <b>{jackpots.get('slots', 0)}</b>
        Выигрыши: <b>{wins.get('slots', 0)}</b>
        Попытки: <b>{tries.get('slots', 0)}</b>"""
        
    elif category == "dice":
        text = f"""🎲 <b>СТАТИСТИКА КУБИКА</b>
        Выигрыши: <b>{wins.get('dice', 0)}</b>
        Попытки: <b>{tries.get('dice', 0)}</b>"""
        
    elif category == "foot":
        text = f"""⚽ <b>СТАТИСТИКА ФУТБОЛА</b>
        Выигрыши: <b>{wins.get('foot', 0)}</b>
        Попытки: <b>{tries.get('foot', 0)}</b>"""

    elif category == "bowl":
        text = f"""🎳 <b>СТАТИСТИКА БОУЛИНГА</b>
        Выигрыши: <b>{wins.get('bowl', 0)}</b>
        Попытки: <b>{tries.get('bowl', 0)}</b>"""

    elif category == "bask":
        text = f"""🏀 <b>СТАТИСТИКА БАСКЕТБОЛА</b>
        Выигрыши: <b>{wins.get('bask', 0)}</b>
        Попытки: <b>{tries.get('bask', 0)}</b>"""

    elif category == "dart":
        text = f"""🎯 <b>СТАТИСТИКА ДАРТСА</b>
        Выигрыши: <b>{wins.get('dart', 0)}</b>
        Попытки: <b>{tries.get('dart', 0)}</b>"""

    elif category == "reset":
        USERS.reset_user(callback.from_user.id, callback.message.chat.id)
        await callback.message.edit_text(f'✅ Статистика игрока {f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.full_name} <b>сброшена</b>',)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🎰", callback_data="stats-slots"), InlineKeyboardButton("🎲", callback_data="stats-dice"), InlineKeyboardButton("⚽", callback_data="stats-foot")],
        [InlineKeyboardButton("🎳", callback_data="stats-bowl"), InlineKeyboardButton("🏀", callback_data="stats-bask"), InlineKeyboardButton("🎯", callback_data="stats-dart")],
        [InlineKeyboardButton("♻️ Сбросить", callback_data="stats-reset")],
    ])

    await callback.message.edit_text(text, parse_mode='HTML', reply_markup=keyboard)

# Админ панель
@DP.callback_query_handler(lambda c: c.data == 'admin')
async def admin_panel(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('♻️ Сбросить статистику чата', callback_data='admin-reset-chat'))
    keyboard.add(InlineKeyboardButton('📊 Статистика чата', callback_data='admin-chat-stats'))
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='back-to-main'))

    await callback.message.edit_text(
        "⚙️ <b>Панель администратора</b>\nВыберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

@DP.callback_query_handler(lambda c: c.data == 'admin-reset-chat')
async def admin_reset_chat(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    USERS.reset_chat(callback.message.chat.id)
    
    # Добавляем кнопку назад после сброса
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    await callback.message.edit_text("✅ <b>Статистика всего чата сброшена</b>", reply_markup=keyboard)
    await callback.answer()

@DP.callback_query_handler(lambda c: c.data == 'admin-chat-stats')
async def admin_chat_stats(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    chat_id = callback.message.chat.id
    tries_data = USERS.get_all('tries', chat_id)
    wins_data = USERS.get_all('wins', chat_id)
    jackpots_data = USERS.get_all('jackpots', chat_id)

    total_tries = sum(sum(val for k, val in item.items() if k not in ['id', 'chat_id', 'timestamp'] and val is not None) for item in tries_data)
    total_wins = sum(sum(val for k, val in item.items() if k not in ['id', 'chat_id', 'timestamp'] and val is not None) for item in wins_data)
    total_jackpots = sum(item.get('slots', 0) for item in jackpots_data if item.get('slots') is not None)
    total_players = len(set(item['id'] for item in tries_data))

    text = f"""📊 <b>Статистика чата</b>

👥 <b>Игроков</b>: {total_players}
🎰 <b>Попыток</b>: {total_tries}
✅ <b>Выигрышей</b>: {total_wins}
⭐ <b>Джекпотов</b>: {total_jackpots}
📈 <b>Винрейт</b>: {round((total_wins / total_tries * 100) if total_tries > 0 else 0, 1)}%"""

    # Добавляем кнопку назад
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@DP.callback_query_handler(lambda c: c.data == 'back-to-main')
async def back_to_main(callback: types.CallbackQuery):
    await main_menu(callback.message)

@DP.message_handler(commands=['congratulate'])
async def congratulate(message: types.Message):
    user = USERS.get('users', message.from_user.id)
    USERS.set('users', message.from_user.id, None, 'congratulate', False if user['congratulate'] else True)

    await BOT.send_message(
        message.chat.id,
        f'✅ <b>Настройка сохранена</b>\n<i>Переключено на <b>{"ДА" if not user["congratulate"] else "НЕТ"}</b></i>',
        message_thread_id=message.message_thread_id
    )

# Команда для добавления админов
@DP.message_handler(commands=['addadmin'])
async def add_admin(message: types.Message):
    # Только существующие админы могут добавлять новых
    if not USERS.is_admin(message.from_user.id):
        return

    try:
        user_id = int(message.get_args())
        USERS.add_admin(user_id)
        await message.reply(f"✅ Пользователь {user_id} добавлен как администратор")
    except ValueError:
        await message.reply("❌ Используйте: /addadmin <user_id>")

if __name__ == '__main__':
    MessagesHandler(DP, BOT, GAMES, USERS)
    RatingHandler(DP, BOT, USERS)


    executor.start_polling(DP, skip_updates=False, allowed_updates=["message", "callback_query"])

