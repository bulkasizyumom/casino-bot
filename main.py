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
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🏆 Рейтинги', callback_data='rating_main'))
    
    # Добавляем кнопку для админов
    if USERS.is_admin(message.from_user.id):
        keyboard.add(InlineKeyboardButton('⚙️ Админ', callback_data='admin'))

    await BOT.send_message(
        message.chat.id,
        f"""🎰 <b>Здравствуйте, {f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name}!</b>

Добро пожаловать в казино-бот! Используйте кнопки ниже для навигации.

ℹ️ <b>Информация:</b> /info""",
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

# info command

@DP.message_handler(commands=['info'])
async def info_command(message: types.Message):
    text = """🎰 <b>Я — Дилер. Хозяин "Подземелья", распорядитель истинных желаний.</b> 

Я — причина, по которой вашего времени становится меньше. Удача любит смелых, а я... их проигрыши.

<b>ВАРИАНТЫ:</b>
🎰 - собери три одинаковых знака, если хватит терпения;
🎲 - шесть граней, шесть чисел, только 1 - победа;
🎯 - дротиком в яблочко или на пол тряпочкой?
🎳 - думаешь, легко получить страйк?
⚽ - горизонтальный баскетбол; 
🏀 - вертикальный футбол;

И не забывай: я помню ВСЁ. Каждые сутки, недели - ни одна попытка не скроется от моих глаз.

<b>Используйте /games чтобы начать играть</b>"""

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🏆 Рейтинги', callback_data='rating_main'))
    
    if USERS.is_admin(message.from_user.id):
        keyboard.add(InlineKeyboardButton('⚙️ Админ', callback_data='admin'))

    await BOT.send_message(
        message.chat.id, text,
        message_thread_id=message.message_thread_id,
        reply_markup=keyboard
    )

# Админ панель
@DP.callback_query_handler(lambda c: c.data == 'admin')
async def admin_panel(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('♻️ Сбросить рейтинги за сутки', callback_data='admin-reset-day'))
    keyboard.add(InlineKeyboardButton('♻️ Сбросить рейтинги за неделю', callback_data='admin-reset-week'))
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='back-to-main'))

    await callback.message.edit_text(
        "⚙️ <b>Панель администратора</b>\nВыберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

@DP.callback_query_handler(lambda c: c.data in ['admin-reset-day', 'admin-reset-week'])
async def admin_reset_ratings(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    period = 'day' if callback.data == 'admin-reset-day' else 'week'
    period_name = 'сутки' if period == 'day' else 'неделю'
    
    # Здесь будет логика сброса рейтингов за указанный период
    # Пока просто отправляем сообщение
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    await callback.message.edit_text(
        f"✅ <b>Рейтинги за {period_name} сброшены</b>\n\n"
        f"<i>Примечание: В текущей реализации требуется дополнительная настройка для полнофункционального сброса рейтингов по периодам.</i>",
        reply_markup=keyboard
    )
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
