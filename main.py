import json, os, time, logging

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# 🔒 БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ТОКЕНА
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in environment variables!")

print("✅ Bot token loaded successfully from environment variables")

BOT = Bot(token=BOT_TOKEN, parse_mode='HTML')
STORAGE = MemoryStorage()
DP = Dispatcher(BOT, storage=STORAGE)

DATABASE = Database('data.db')
USERS = Users(DATABASE)

GAMES = {
    '🎰': {'name': 'slots', 'win': [1, 22, 43], 'jackpot': 64},
    '🏀': {'name': 'bask',  'win': [4, 5]},
    '🎯': {'name': 'dart',  'win': [6]},
    '⚽️': {'name': 'foot',  'win': [3, 5]},
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
        # Регистрируем пользователя на ЛЮБОЕ сообщение (включая dice)
        if message.from_user and not USERS.get('users', message.from_user.id):
            USERS.add(message.from_user.id, message.from_user.full_name)

DP.middleware.setup(UserRegistrationMiddleware())

# main menu handler
@DP.message_handler(commands=['casino', 'start'])
async def main_menu(message: types.Message):
    # 🔥 ЛОГИРУЕМ КОМАНДЫ /start И /casino
    logger.info(
        f"🏠 КОМАНДА: "
        f"UserID={message.from_user.id}, "
        f"Name={message.from_user.full_name}, "
        f"Command={message.text}"
    )
    
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

# ... ВСЕ ОСТАЛЬНЫЕ ФУНКЦИИ БЕЗ ИЗМЕНЕНИЙ ...

if __name__ == '__main__':
    MessagesHandler(DP, BOT, GAMES, USERS)
    RatingHandler(DP, BOT, USERS)

    print("🤖 Бот запущен и работает...")
    print("Для остановки нажми Ctrl+C")
    
    executor.start_polling(DP, skip_updates=False, allowed_updates=["message", "callback_query"])
