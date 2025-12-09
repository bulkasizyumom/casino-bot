import json, os, time, logging
from datetime import datetime, timedelta
import asyncio

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

GAMES = {
    '🎰': {'name': 'slots', 'win': [1, 22, 43], 'jackpot': 64},
    '🏀': {'name': 'bask',  'win': [4, 5]},
    '🎯': {'name': 'dart',  'win': [6]},
    '⚽️': {'name': 'foot',  'win': [3, 5]},
    '🎳': {'name': 'bowl',  'win': [6]},
    '🎲': {'name': 'dice',  'win': [1]},
}

# Добавляем админов
ADMIN_IDS = [1773287874]  # Только вы как админ
for admin_id in ADMIN_IDS:
    USERS.add_admin(admin_id)

# 🔥 СПИСОК ИЗВЕСТНЫХ УЧАСТНИКОВ
KNOWN_USERS = {
    1014610866: "Рома",  # Изменили Анжело на Рома
    5208717293: "Лиза", 
    772615435: "Саша ʕ≧ᴥ≦ʔ",
    1789058587: "Владимир",
    751379478: "Степа",
    1995856157: "Санек",
    5928889926: "Катя"  # Добавили Катю
}

# Состояния для FSM
class HelpState(StatesGroup):
    waiting_for_help_message = State()

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
                    minutes_left = block_info.get('minutes_left', 0)
                    
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
        if callback_query.data == 'help_send_message':
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
⚽️ <b>Футбол:</b> /foot
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

Я — причина, по которой вашего времени становится меньше. Удача любит смелых, а я... их проигрыши.

<b>ВАРИАНТЫ:</b>
🎰 - собери три одинаковых знака, если хватит терпения;
🎲 - шесть граней, шесть чисел, только 1 - победа;
🎯 - дротиком в яблочко или на пол тряпочкой?
🎳 - думаешь, легко получить страйк?
⚽️ - горизонтальный баскетбол; 
🏀 - вертикальный футбол;

И не забывай: я помню ВСЁ. Каждые сутки, недели - ни одна попытка не скроется от моих глаз."""

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🏆 Рейтинги', callback_data='rating_main'))
    
    if USERS.is_admin(message.from_user.id):
        keyboard.add(InlineKeyboardButton('⚙️ Админ', callback_data='admin'))

    await BOT.send_message(
        message.chat.id, text,
        message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None,
        reply_markup=keyboard
    )

# Команда помощи для заблокированных пользователей
@DP.message_handler(commands=['help'])
async def help_command(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, заблокирован ли пользователь
    is_blocked = USERS.is_user_blocked(user_id, chat_id)
    
    if is_blocked:
        # Создаем клавиатуру для заблокированного пользователя
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton('📨 Написать сообщение помощи', callback_data='help_send_message')
        )
        
        await BOT.send_message(
            chat_id,
            "🚫 <b>Вы заблокированы!</b>\n\n"
            "Если вы считаете, что блокировка была несправедливой, "
            "вы можете отправить сообщение администратору с объяснением ситуации.\n\n"
            "Ваше сообщение будет рассмотрено в кратчайшие сроки.",
            reply_markup=keyboard,
            message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None
        )
    else:
        await BOT.send_message(
            chat_id,
            "ℹ️ <b>Команды бота:</b>\n\n"
            "/casino или /start - Главное меню\n"
            "/games - Список игр\n"
            "/info - Информация о боте\n"
            "/help - Помощь\n"
            "/mystreak - Ваши серии побед\n"
            "/congratulate - Включить/выключить поздравления",
            message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None
        )

# Обработчик кнопки помощи
@DP.callback_query_handler(lambda c: c.data == 'help_send_message')
async def help_send_message_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    # Проверяем, заблокирован ли пользователь
    if not USERS.is_user_blocked(user_id, chat_id):
        await callback.answer("Вы не заблокированы", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📝 <b>Напишите ваше сообщение помощи:</b>\n\n"
        "Опишите, почему вы считаете блокировку несправедливой.\n"
        "Максимум 500 символов.\n\n"
        "❌ <i>Отмена: /cancel</i>"
    )
    
    await HelpState.waiting_for_help_message.set()
    await callback.answer()

# Обработчик сообщения помощи
@DP.message_handler(state=HelpState.waiting_for_help_message, content_types=ContentType.TEXT)
async def process_help_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, заблокирован ли пользователь
    if not USERS.is_user_blocked(user_id, chat_id):
        await state.finish()
        await message.answer("❌ Вы не заблокированы")
        return
    
    if message.text == '/cancel':
        await state.finish()
        await message.answer("❌ Отправка сообщения отменена.")
        return
    
    # Проверяем длину сообщения
    if len(message.text) > 500:
        await message.answer("❌ Сообщение слишком длинное! Максимум 500 символов.")
        return
    
    # Сохраняем сообщение помощи
    message_id = USERS.add_help_message(user_id, chat_id, message.text)
    
    if message_id:
        # Уведомляем пользователя
        await message.answer(
            "✅ <b>Сообщение отправлено!</b>\n\n"
            "Администратор получил ваше сообщение. "
            "Ожидайте ответа в ближайшее время."
        )
        
        # Уведомляем всех админов
        for admin_id in ADMIN_IDS:
            try:
                await BOT.send_message(
                    admin_id,
                    f"🆘 <b>Новое сообщение помощи от заблокированного пользователя!</b>\n\n"
                    f"👤 <b>Пользователь:</b> {message.from_user.full_name}\n"
                    f"🆔 <b>ID:</b> {user_id}\n"
                    f"💬 <b>Сообщение:</b>\n{message.text}\n\n"
                    f"🕒 <b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            except:
                pass
    else:
        await message.answer("❌ Ошибка при отправке сообщения. Попробуйте позже.")
    
    await state.finish()

# 🔥 ПРОСТАЯ АДМИН ПАНЕЛЬ
@DP.callback_query_handler(lambda c: c.data == 'admin')
async def admin_panel(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton('👥 Заблокировать', callback_data='admin-block-user'),
        InlineKeyboardButton('✅ Разблокировать', callback_data='admin-unblock-user')
    )
    keyboard.add(
        InlineKeyboardButton('📋 Список заблокированных', callback_data='admin-blocked-list'),
        InlineKeyboardButton('♻️ Сбросить рейтинги', callback_data='admin-reset-all')
    )
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='back-to-main'))

    await callback.message.edit_text(
        "⚙️ <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

# Выбор пользователя для блокировки
@DP.callback_query_handler(lambda c: c.data == 'admin-block-user')
async def admin_block_user(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Добавляем кнопки для каждого известного пользователя
    for user_id, name in KNOWN_USERS.items():
        keyboard.add(InlineKeyboardButton(f'👤 {name}', callback_data=f'block_select_user-{user_id}'))
    
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    await callback.message.edit_text(
        "👥 <b>Выберите пользователя для блокировки:</b>",
        reply_markup=keyboard
    )
    await callback.answer()

# Выбор времени блокировки
@DP.callback_query_handler(lambda c: c.data.startswith('block_select_user-'))
async def admin_block_select_time(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    user_id = int(callback.data.split('-')[1])
    user_name = KNOWN_USERS.get(user_id, f"ID {user_id}")
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton('⏰ 15 минут', callback_data=f'block_confirm-{user_id}-15'),
        InlineKeyboardButton('⏰ 30 минут', callback_data=f'block_confirm-{user_id}-30')
    )
    keyboard.add(
        InlineKeyboardButton('⏰ 1 час', callback_data=f'block_confirm-{user_id}-60'),
        InlineKeyboardButton('⏰ 3 часа', callback_data=f'block_confirm-{user_id}-180')
    )
    keyboard.add(
        InlineKeyboardButton('⏰ 6 часов', callback_data=f'block_confirm-{user_id}-360'),
        InlineKeyboardButton('⏰ 12 часов', callback_data=f'block_confirm-{user_id}-720')
    )
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin-block-user'))
    
    await callback.message.edit_text(
        f"👤 <b>Пользователь:</b> {user_name}\n"
        f"🕒 <b>Выберите длительность блокировки:</b>",
        reply_markup=keyboard
    )
    await callback.answer()

# Подтверждение и выполнение блокировки
@DP.callback_query_handler(lambda c: c.data.startswith('block_confirm-'))
async def admin_block_confirm(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    data_parts = callback.data.split('-')
    user_id = int(data_parts[1])
    minutes = int(data_parts[2])
    user_name = KNOWN_USERS.get(user_id, f"ID {user_id}")
    
    # Предполагаем, что блокировка в основном чате
    chat_id = callback.message.chat.id
    
    # Блокируем пользователя
    success = USERS.block_user(user_id, chat_id, "Нарушение правил", minutes)
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад в админку', callback_data='admin'))
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Пользователь заблокирован!</b>\n\n"
            f"👤 <b>Имя:</b> {user_name}\n"
            f"⏳ <b>Длительность:</b> {minutes} минут",
            reply_markup=keyboard
        )
        
        # Уведомляем пользователя без указания ID
        try:
            await BOT.send_message(
                user_id,
                f"🚫 <b>Вы были заблокированы в казино-боте!</b>\n\n"
                f"⏳ <b>Длительность:</b> {minutes} минут\n\n"
                f"Если вы считаете, что блокировка несправедлива, "
                f"используйте команду /help в чате, чтобы написать администратору."
            )
        except:
            pass
    
    await callback.answer()

# Выбор пользователя для разблокировки
@DP.callback_query_handler(lambda c: c.data == 'admin-unblock-user')
async def admin_unblock_user(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    # Получаем список заблокированных пользователей
    chat_id = callback.message.chat.id
    blocked_users = USERS.get_all_blocked_users(chat_id)
    
    if not blocked_users:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
        
        await callback.message.edit_text(
            "📭 <b>Нет заблокированных пользователей</b>",
            reply_markup=keyboard
        )
        await callback.answer()
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for user in blocked_users:
        user_id = user['user_id']
        user_name = KNOWN_USERS.get(user_id, f"Пользователь")
        minutes_left = user.get('minutes_left', 0)
        
        keyboard.add(InlineKeyboardButton(
            f'✅ {user_name} ({minutes_left} мин)', 
            callback_data=f'unblock_user-{user_id}'
        ))
    
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    await callback.message.edit_text(
        "✅ <b>Выберите пользователя для разблокировки:</b>\n\n"
        "<i>В скобках указано оставшееся время блокировки</i>",
        reply_markup=keyboard
    )
    await callback.answer()

# Выполнение разблокировки
@DP.callback_query_handler(lambda c: c.data.startswith('unblock_user-'))
async def admin_unblock_execute(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    user_id = int(callback.data.split('-')[1])
    user_name = KNOWN_USERS.get(user_id, "Пользователь")
    
    # Предполагаем, что разблокировка в основном чате
    chat_id = callback.message.chat.id
    
    # Разблокируем пользователя
    success = USERS.unblock_user(user_id, chat_id)
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад в админку', callback_data='admin'))
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Пользователь разблокирован!</b>\n\n"
            f"👤 <b>Имя:</b> {user_name}",
            reply_markup=keyboard
        )
        
        # Уведомляем пользователя
        try:
            await BOT.send_message(
                user_id,
                "✅ <b>Вы были разблокированы!</b>\n\n"
                "Администратор снял с вас блокировку. Теперь вы можете снова использовать бота."
            )
        except:
            pass
    
    await callback.answer()

# Список заблокированных пользователей
@DP.callback_query_handler(lambda c: c.data == 'admin-blocked-list')
async def admin_blocked_list(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    chat_id = callback.message.chat.id
    blocked_users = USERS.get_all_blocked_users(chat_id)
    
    if not blocked_users:
        text = "📭 <b>Нет заблокированных пользователей</b>"
    else:
        text = "🚫 <b>Заблокированные пользователи:</b>\n\n"
        for i, user in enumerate(blocked_users, 1):
            user_id = user['user_id']
            user_name = KNOWN_USERS.get(user_id, "Пользователь")
            
            minutes_left = user.get('minutes_left', 0)
            
            text += f"{i}. <b>{user_name}</b>\n"
            text += f"   ⏳ <b>Осталось:</b> {minutes_left} минут\n"
            text += f"   🕒 <b>Причина:</b> {user['reason']}\n\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@DP.callback_query_handler(lambda c: c.data == 'admin-reset-all')
async def admin_reset_all_ratings(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    success = USERS.reset_all_stats()

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    if success:
        await callback.message.edit_text(
            "✅ <b>Все рейтинги и серии успешно сброшены!</b>\n\n"
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
    message = types.Message(
        message_id=callback.message.message_id,
        date=callback.message.date,
        chat=callback.message.chat,
        from_user=callback.from_user,
        text='/start'
    )
    await main_menu(message)

@DP.message_handler(commands=['congratulate'])
async def congratulate(message: types.Message):
    user = USERS.get('users', message.from_user.id)
    if user:
        USERS.set('users', message.from_user.id, None, 'congratulate', False if user['congratulate'] else True)

        await BOT.send_message(
            message.chat.id,
            f'✅ <b>Настройка сохранена</b>\n<i>Переключено на <b>{"ДА" if not user["congratulate"] else "НЕТ"}</b></i>',
            message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None
        )

# Команда для проверки текущей серии
@DP.message_handler(commands=['mystreak'])
async def my_streak(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    text_lines = ["🔥 <b>Ваши текущие серии побед:</b>\n"]
    
    games_list = ['slots', 'dice', 'foot', 'bowl', 'bask', 'dart']
    has_streaks = False
    
    for game in games_list:
        streaks_data = USERS.get_win_streaks(chat_id, game)
        for streak in streaks_data:
            if streak['id'] == user_id and streak['max_streak'] > 0:
                game_names = {
                    'slots': '🎰 Слоты',
                    'dice': '🎲 Кубик',
                    'foot': '⚽️ Футбол',
                    'bowl': '🎳 Боулинг',
                    'bask': '🏀 Баскетбол',
                    'dart': '🎯 Дартс'
                }
                text_lines.append(f"{game_names.get(game, game)}: <b>{streak['max_streak']}</b>")
                has_streaks = True
    
    if not has_streaks:
        text_lines.append("\n📊 <i>У вас пока нет серий побед</i>")
    
    await BOT.send_message(
        message.chat.id,
        '\n'.join(text_lines),
        message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None
    )

if __name__ == '__main__':
    MessagesHandler(DP, BOT, GAMES, USERS)
    RatingHandler(DP, BOT, USERS)

    print("🤖 Бот запущен и работает...")
    print("Для остановки нажми Ctrl+C")
    
    executor.start_polling(DP, skip_updates=False, allowed_updates=["message", "callback_query"])

