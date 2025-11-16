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

# ⚠️ ДИАГНОСТИКА - добавьте в самое начало
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("🚀 ЗАПУСК БОТА - ДИАГНОСТИКА")
print("=" * 50)

# variables

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
print(f"🔐 Токен: {BOT_TOKEN[:10]}...") if BOT_TOKEN else print("❌ Токен не найден!")

# СОЗДАНИЕ ОБЪЕКТА БОТА
BOT = Bot(token=BOT_TOKEN, parse_mode='HTML')

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

print(f"🎮 Игры: {list(GAMES.keys())}")

# Добавляем админов (замените на реальные ID)
ADMIN_IDS = [1773287874, 1995856157]  # Замените на реальные ID администраторов
for admin_id in ADMIN_IDS:
    USERS.add_admin(admin_id)

print(f"👑 Админы: {ADMIN_IDS}")

# user register

class UserRegistrationMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        print(f"📨 Сообщение от {message.from_user.id}: {message.content_type}")
        if not USERS.get('users', message.from_user.id):
            USERS.add(message.from_user.id, message.from_user.full_name)
            print(f"✅ Зарегистрирован: {message.from_user.id}")

DP.middleware.setup(UserRegistrationMiddleware())

# ДИАГНОСТИЧЕСКИЙ обработчик ВСЕХ сообщений
@DP.message_handler(content_types=ContentType.ANY)
async def debug_all_messages(message: types.Message):
    print(f"🔍 ВСЕ СООБЩЕНИЯ:")
    print(f"   Чат: {message.chat.id} | Пользователь: {message.from_user.id}")
    print(f"   Тип: {message.content_type} | Текст: {message.text}")
    if message.dice:
        print(f"   🎲 DICE: {message.dice.emoji} = {message.dice.value}")
    print("---")

# main menu handler
@DP.message_handler(commands=['casino', 'start'])
async def main_menu(message: types.Message):
    print(f"🎰 Команда /start от {message.from_user.id}")
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

И не забывай: я помню ВСЁ. Каждые сутки, недели - ни одна попытка не скроется от моих глаз."""

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
    keyboard.add(InlineKeyboardButton('♻️ Сбросить все рейтинги', callback_data='admin-reset-all'))
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='back-to-main'))

    await callback.message.edit_text(
        "⚙️ <b>Панель администратора</b>\nВыберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

@DP.callback_query_handler(lambda c: c.data == 'admin-reset-all')
async def admin_reset_all_ratings(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    # Используем метод из Users для сброса всей статистики
    success = USERS.reset_all_stats()

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    if success:
        await callback.message.edit_text(
            "✅ <b>Все рейтинги успешно сброшены!</b>\n\n"
            "Вся статистика обнулена. Теперь можно начинать новую статистику с чистого листа.",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Ошибка при сбросе рейтингов</b>\n\n"
            "Попробуйте позже или проверьте логи.",
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
    print("🎯 Запуск обработчиков...")
    MessagesHandler(DP, BOT, GAMES, USERS)
    RatingHandler(DP, BOT, USERS)

    # ⚠️ ДОБАВЬТЕ ЭТОТ КОД - принудительный сброс webhook
    import asyncio
    async def reset_webhook():
        try:
            await BOT.delete_webhook()
            print("✅ Webhook сброшен!")
        except Exception as e:
            print(f"❌ Ошибка сброса webhook: {e}")
    
    asyncio.run(reset_webhook())

    print("✅ Бот запущен! Ожидаю сообщения...")
    print("=" * 50)
    
    executor.start_polling(DP, skip_updates=False, allowed_updates=["message", "callback_query"])
