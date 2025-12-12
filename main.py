import json, os, time, logging
from datetime import datetime, timedelta
import asyncio
import schedule
import threading

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ContentType
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

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

# 🔥 ИСПРАВЛЕНИЕ: Исправляем эмодзи футбола (был ⚽️, стал 🏈)
GAMES = {
    '🎰': {'name': 'slots', 'win': [1, 22, 43], 'jackpot': 64},
    '🏀': {'name': 'bask',  'win': [4, 5]},
    '🎯': {'name': 'dart',  'win': [6]},
    '🏈': {'name': 'foot',  'win': [3, 5]},  # 🔥 ИСПРАВЛЕНИЕ: меняем ⚽️ на 🏈
    '🎳': {'name': 'bowl',  'win': [6]},
    '🎲': {'name': 'dice',  'win': [1]},
}

# 🔥 ФУНКЦИЯ ДЛЯ ОБНОВЛЕНИЯ ПЕРИОДИЧЕСКОЙ СТАТИСТИКИ
def check_and_reset_periodic_stats():
    """Проверяет и обновляет периодическую статистику при смене дня/недели"""
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")
        
        logger.info(f"Проверка периодической статистики. Дата: {current_date}, Начало недели: {current_week_start}")
        
        # Здесь можно добавить логику для очистки устаревших данных
        # если это необходимо для вашей реализации
        
        # Для тестирования - логируем время
        logger.info(f"Текущее время: {datetime.now().strftime('%H:%M:%S')}")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке периодической статистики: {e}")

# 🔥 ФУНКЦИЯ ДЛЯ ЗАПУСКА ПЛАНИРОВЩИКА
def run_scheduler():
    """Запускает планировщик для периодических задач"""
    # Проверяем каждый час, чтобы не пропустить полночь
    schedule.every().hour.do(check_and_reset_periodic_stats)
    
    # Также проверяем каждый понедельник в 00:00 для недельной статистики
    schedule.every().monday.at("00:00").do(check_and_reset_periodic_stats)
    
    while True:
        schedule.run_pending()
        time.sleep(3600)  # Проверяем каждый час

# 🔥 ЗАПУСКАЕМ ПЛАНИРОВЩИК В ОТДЕЛЬНОМ ПОТОКЕ
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# Добавляем админов
ADMIN_IDS = [1773287874,1995856157] 
for admin_id in ADMIN_IDS:
    USERS.add_admin(admin_id)

# 🔥 СПИСОК ИЗВЕСТНЫХ УЧАСТНИКОВ
KNOWN_USERS = {
    1014610866: "Рома",  
    5208717293: "Лиза", 
    772615435: "Саша ʕ≧ᴥ≦ʔ",
    1789058587: "Владимир",
    751379478: "Степа",
    1995856157: "Санек",
    5928889926: "Катя" 
}

# 🔥 НОВЫЙ МИДЛВАРЬ ДЛЯ РУЧНОЙ БЛОКИРОВКИ ПОЛЬЗОВАТЕЛЕЙ
class BlockedUsersMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Исключаем команду /help из блокировки
        if message.text and message.text.lower() == '/help':
            return
        
        # Проверяем ручную блокировку в базе данных
        if USERS.is_user_blocked(user_id, chat_id):
            logger.warning(f"🚫 РУЧНАЯ БЛОКИРОВКА сообщения: UserID={user_id}, ChatID={chat_id}")
            
            # Для команд /start и /casino отправляем сообщение о блокировке
            if message.text and message.text.lower() in ['/start', '/casino']:
                block_info = USERS.get_block_info(user_id, chat_id)
                if block_info:
                    from datetime import datetime
                    end_time = datetime.strptime(block_info['end'], '%Y-%m-%d %H:%M:%S')
                    remaining = end_time - datetime.now()
                    minutes_left = int(remaining.total_seconds() / 60)
                    
                    # 🔥 УПРОЩЕННОЕ СООБЩЕНИЕ О БЛОКИРОВКЕ
                    warning_msg = await BOT.send_message(
                        chat_id,
                        f'🚫 Пользователь @{message.from_user.username if message.from_user.username else message.from_user.full_name} заблокирован!\n'
                        f'⏳ <b>Разблокировка через:</b> {minutes_left} минут',
                        message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None
                    )
                    
                    await asyncio.sleep(5)
                    try:
                        await warning_msg.delete()
                    except:
                        pass
            
            # Удаляем сообщение
            try:
                await message.delete()
            except:
                pass
            
            # Полностью прерываем обработку сообщения
            raise CancelHandler()
    
    async def on_pre_process_callback_query(self, callback_query: types.CallbackQuery, data: dict):
        user_id = callback_query.from_user.id
        chat_id = callback_query.message.chat.id
        
        # Исключаем кнопку помощи из блокировки
        if callback_query.data == 'help_send_request':
            return
            
        if USERS.is_user_blocked(user_id, chat_id):
            logger.warning(f"🚫 РУЧНАЯ БЛОКИРОВКА callback: UserID={user_id}")
            await callback_query.answer("❌ Вы заблокированы в этом чате", show_alert=True)
            raise CancelHandler()

class UserRegistrationMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        if not USERS.get('users', message.from_user.id):
            USERS.add(message.from_user.id, message.from_user.full_name)

# 🔥 РЕГИСТРИРУЕМ МИДЛВАРИ В ПРАВИЛЬНОМ ПОРЯДКЕ
DP.middleware.setup(BlockedUsersMiddleware())  # ПЕРВЫЙ - ручная блокировка
DP.middleware.setup(UserRegistrationMiddleware())  # ВТОРОЙ - регистрация

# main menu handler
@DP.message_handler(commands=['casino', 'start'])
async def main_menu(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    logger.info(
        f"🏠 КОМАНДА: "
        f"UserID={user_id}, "
        f"Name={message.from_user.full_name}, "
        f"Command={message.text}"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🏆 Рейтинги', callback_data='rating_main'))
    
    # Добавляем кнопку для админов
    if USERS.is_admin(user_id):
        keyboard.add(InlineKeyboardButton('⚙️ Админ', callback_data='admin'))

    await BOT.send_message(
        chat_id,
        f"""🎰 <b>Здравствуйте, {f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name}!</b>

Добро пожаловать в казино-бот! Используйте кнопки ниже для навигации.

ℹ️ <b>Информация:</b> /info""",
        message_thread_id = message.message_thread_id if hasattr(message, 'message_thread_id') else None,
        reply_markup=keyboard
    )

# games
@DP.message_handler(commands=['games'])
async def games(message: types.Message):
    text = f"""🎰 <b>Слоты:</b> /slots
🎲 <b>Кубик:</b> /dice
🏈 <b>Футбол:</b> /foot  🔥 ИСПРАВЛЕНО
🎳 <b>Боулинг:</b> /bowl
🏀 <b>Баскетбол:</b> /bask
🎯 <b>Дартс:</b> /dart"""

    await BOT.send_message(
        message.chat.id, text,
        message_thread_id = message.message_thread_id if hasattr(message, 'message_thread_id') else None
    )

# info command
@DP.message_handler(commands=['info'])
async def info_command(message: types.Message):
    text = """🎰 <b>Я — Дилер. Хозяин "Подземелья", распорядитель истинных желаний.</b> 

Я
