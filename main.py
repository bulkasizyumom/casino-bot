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
messages_handler = None 
rating_handler = None

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

# 🔥 ИСПРАВЛЕНИЕ: Добавляем оба варианта эмодзи футбола
GAMES = {
    '🎰': {'name': 'slots', 'win': [1, 22, 43], 'jackpot': 64},
    '🏀': {'name': 'bask',  'win': [4, 5]},
    '🎯': {'name': 'dart',  'win': [6]},
    '⚽️': {'name': 'foot',  'win': [3, 5]},  
    '⚽': {'name': 'foot',  'win': [3, 5]},  
    '🎳': {'name': 'bowl',  'win': [6]},
    '🎲': {'name': 'dice',  'win': [1]},
}

# 🔥 УБРАНА НОВОГОДНЯЯ ТЕМАТИКА
def get_greeting():
    """Возвращает приветствие"""
    return "🎲"

# 🔥 ФУНКЦИЯ ДЛЯ ОБНОВЛЕНИЯ ПЕРИОДИЧЕСКОЙ СТАТИСТИКИ
def check_and_reset_periodic_stats():
    """Проверяет и обновляет периодическую статистику при смене дня/недели"""
    try:
        current_datetime = datetime.now()
        current_date = current_datetime.strftime("%Y-%m-%d")
        current_time = current_datetime.strftime("%H:%M")
        current_weekday = current_datetime.weekday()  # 0 - понедельник, 6 - воскресенье
        
        # Логируем только при реальных сбросах статистики, а не каждую минуту
        stats_reset = False
        
        # Проверяем, если сейчас 00:00 - сбрасываем дневную статистику
        if current_time == "00:00":
            logger.info("🌙 Полночь! Сбрасываем дневную статистику")
            USERS.reset_daily_streaks()
            stats_reset = True
        
        # Проверяем, если сейчас понедельник 00:00 - сбрасываем недельную статистику
        if current_time == "00:00" and current_weekday == 0:
            logger.info("📅 Понедельник! Сбрасываем недельную статистику")
            USERS.reset_weekly_streaks()
            stats_reset = True
        
        # Очищаем старые статистики раз в день (только в полночь)
        if current_time == "00:00":
            USERS.cleanup_old_period_stats()
            stats_reset = True
        
        # Логируем только если произошли изменения
        if stats_reset:
            logger.info(f"Периодическая статистика обновлена. Дата: {current_date}")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке периодической статистики: {e}")

# 🔥 ФУНКЦИЯ ДЛЯ ЗАПУСКА ПЛАНИРОВЩИКА
def run_scheduler():
    """Запускает планировщик для периодических задач"""
    # Проверяем каждую минуту для точного срабатывания в 00:00
    schedule.every().minute.do(check_and_reset_periodic_stats)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Проверяем каждую минуту

# 🔥 ЗАПУСКАЕМ ПЛАНИРОВЩИК В ОТДЕЛЬНОМ ПОТОКЕ
scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
scheduler_thread.start()

# 🔥 ИСПРАВЛЕНИЕ: Добавляем Саню в админы
ADMIN_IDS = [1773287874, 1995856157]  
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
    5928889926: "Катя",
    5579075857: "Катя Арланова",
    1062670498: "Даша",
    838369068: "Федя"
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
        
        # 🔥 ИСКЛЮЧАЕМ ВСЕ КНОПКИ ПОМОЩИ ИЗ БЛОКИРОВКИ
        help_callbacks = [
            'help_select_reason',
            'help_cancel',
            'help_send_request'
        ]
        
        # Добавляем все кнопки с причинами
        for reason in ['blocking_error', 'too_long', 'explain_position', 'technical_issue']:
            help_callbacks.append(f'help_reason_{reason}')
        
        # Если это кнопка помощи - пропускаем блокировку
        if callback_query.data in help_callbacks or callback_query.data.startswith('help_reason_'):
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
    
    # 🔥 ИСПРАВЛЕНИЕ: Проверяем из базы данных, а не только по списку ADMIN_IDS
    is_admin_user = USERS.is_admin(user_id) or user_id in ADMIN_IDS
    
    logger.info(
        f"🏠 КОМАНДА: "
        f"UserID={user_id}, "
        f"Name={message.from_user.full_name}, "
        f"Command={message.text}, "
        f"IsAdmin={is_admin_user}"
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🏆 Рейтинги', callback_data='rating_main'))
    keyboard.add(InlineKeyboardButton('🎯 Соревнования', callback_data='competition_main'))
    
    # 🔥 ИСПРАВЛЕНИЕ: Используем проверку из базы данных
    if is_admin_user:
        keyboard.add(InlineKeyboardButton('⚙️ Админ', callback_data='admin'))

    await BOT.send_message(
        chat_id,
        f"""<b>Здравствуйте, {f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name}!</b>

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
🎯 <b>Дартс:</b> /dart

<i>Желаем удачи в играх!</i>"""

    await BOT.send_message(
        message.chat.id, text,
        message_thread_id = message.message_thread_id if hasattr(message, 'message_thread_id') else None
    )

# info command
@DP.message_handler(commands=['info'])
async def info_command(message: types.Message):
    user_id = message.from_user.id
    # 🔥 ИСПРАВЛЕНИЕ: Проверяем из базы данных
    is_admin_user = USERS.is_admin(user_id) or user_id in ADMIN_IDS
    
    text = f"""🎲 <b>Я — Дилер. Хозяин "Подземелья", распорядитель истинных желаний.</b> 

✨ Я — причина, по которой вашего времени становится меньше. Удача любит смелых, а я... их проигрыши.

<b>ВАРИАНТЫ:</b>
🎰 - собери три одинаковых знака, если хватит терпения;
🎲 - шесть граней, шесть чисел, только 1 - победа;
🎯 - дротиком в яблочко или на пол тряпочкой?
🎳 - думаешь, легко получить страйк?
⚽️ - горизонтальный баскетбол; 
🏀 - вертикальный футбол;

🎁 И не забывай: я помню ВСЁ. Каждые сутки, недели - ни одна попытка не скроется от моих глаз.

🏅 <b>НОВОЕ: Соревнования!</b> Проверь свои очки по формуле из таблицы."""

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🏆 Рейтинги', callback_data='rating_main'))
    keyboard.add(InlineKeyboardButton('🎯 Соревнования', callback_data='competition_main'))
    
    # 🔥 ИСПРАВЛЕНИЕ: Используем проверку из базы данных
    if is_admin_user:
        keyboard.add(InlineKeyboardButton('⚙️ Админ', callback_data='admin'))

    await BOT.send_message(
        message.chat.id, text,
        message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None,
        reply_markup=keyboard
    )


# 🔥 НОВЫЙ ХЕНДЛЕР ДЛЯ СОРЕВНОВАНИЙ
@DP.callback_query_handler(lambda c: c.data == 'competition_main')
async def competition_main(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton('🏅 Общий рейтинг', callback_data='competition_rating'),
        InlineKeyboardButton('👤 Мои очки', callback_data='competition_my_points')
    )
    # Убрана кнопка "📊 Формула подсчета"
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='back-to-main'))

    await callback.message.edit_text(
        f"🎯 <b>Соревнования</b>",
        reply_markup=keyboard
    )
    await callback.answer()

# Показ рейтинга соревнований
@DP.callback_query_handler(lambda c: c.data == 'competition_rating')
async def competition_rating(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    # Получаем рейтинг
    rating_data = USERS.get_competition_rating(chat_id)
    
    if not rating_data:
        text = "📊 <i>Пока нет статистики для соревнований.</i>\n\nСыграйте в игры, чтобы набрать очки!"
    else:
        text = f"🏅 <b>РЕЙТИНГ УЧАСТНИКОВ</b>\n\n"
        
        # Находим место текущего пользователя
        user_place = "–"
        user_points = 0
        
        for i, (uid, name, points) in enumerate(rating_data, 1):
            if uid == user_id:
                user_place = i
                user_points = points
        
        text += f"👤 <b>Ваше место:</b> {user_place}\n"
        text += f"⭐️ <b>Ваши очки:</b> {user_points}\n\n"
        
        text += "<b>ТОП-10 участников:</b>\n"
        
        for i, (uid, name, points) in enumerate(rating_data[:10], 1):
            medal = ""
            if i == 1:
                medal = "🥇 "
            elif i == 2:
                medal = "🥈 "
            elif i == 3:
                medal = "🥉 "
            
            text += f"<b>{i}.</b> {medal}{name} - <b>{points}</b> очков\n"
        
        if len(rating_data) > 10:
            text += f"\n<i>Всего участников: {len(rating_data)}</i>"
        
        text += f"\n\n<i>Удачи в соревнованиях!</i>"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='competition_main'))
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Мои очки
@DP.callback_query_handler(lambda c: c.data == 'competition_my_points')
async def competition_my_points(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    points = USERS.get_competition_points(user_id, chat_id)
    
    # Получаем детальную статистику
    tries_data = USERS.get('tries', user_id, chat_id)
    wins_data = USERS.get('wins', user_id, chat_id)
    
    if not tries_data or not wins_data:
        text = "📊 <i>У вас пока нет статистики для соревнований.</i>\n\nСыграйте в игры, чтобы набрать очки!"
    else:
        text = f"⭐️ <b>ВАША СТАТИСТИКА ДЛЯ СОРЕВНОВАНИЙ</b>\n\n"
        text += f"🎯 <b>Общие очки:</b> <code>{points}</code>\n\n"
        
        # Статистика по играм
        games_stats = [
            ('🎰 Слоты', 'slots'),
            ('🎲 Кубик', 'dice'),
            ('🎯 Дартс', 'dart'),
            ('🎳 Боулинг', 'bowl'),
            ('⚽️ Футбол', 'foot'),
            ('🏀 Баскетбол', 'bask')
        ]
        
        for game_name, game_key in games_stats:
            tries = tries_data.get(game_key, 0)
            wins = wins_data.get(game_key, 0)
            
            if tries > 0:
                winrate = (wins / tries) * 100
                text += f"{game_name}: {tries} попыток, {wins} побед ({winrate:.1f}%)\n"
    
    text += f"\n<i>Удачи в соревнованиях!</i>"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🏅 Общий рейтинг', callback_data='competition_rating'))
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='competition_main'))
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()



# 🔥 ОБНОВЛЕННАЯ КОМАНДА ПОМОЩИ
@DP.message_handler(commands=['help'])
async def help_command(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Проверяем, заблокирован ли пользователь
    if not USERS.is_user_blocked(user_id, chat_id):
        # Если не заблокирован, показываем обычное сообщение (как в старой версии)
        await BOT.send_message(
            chat_id,
            "ℹ️ <b>Если вас заблокировали и вы не согласны с этим</b>\n\n"
            "Нажмите на кнопку ниже, чтобы отправить заявку администратору.\n"
            "Ваша заявка будет рассмотрена в кратчайшие сроки.\n\n"
            "<i>Эта кнопка доступна только заблокированным пользователям.</i>",
            message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None
        )
        return
    
    # Если пользователь заблокирован, показываем меню помощи с выбором причины
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton('🚫 Выбрать причину для обжалования', callback_data='help_select_reason')
    )
    
    await BOT.send_message(
        chat_id,
        "🚫 <b>Вы заблокированы в этом чате</b>\n\n"
        "Если вы не согласны с блокировкой, вы можете отправить заявку на рассмотрение администратору.\n\n"
        "Нажмите на кнопку ниже, чтобы выбрать причину для обжалования блокировки.",
        reply_markup=keyboard,
        message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None
    )

# Выбор причины блокировки
@DP.callback_query_handler(lambda c: c.data == 'help_select_reason')
async def help_select_reason(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    # 🔥 Только готовые варианты (без "своей причины")
    reasons = [
        ("🚫 Блокировка по ошибке", "blocking_error"),
        ("⏰ Слишком долгий срок блокировки", "too_long"),
        ("📝 Хочу объяснить свою позицию", "explain_position"),
        ("🔧 Техническая проблема", "technical_issue")
    ]
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for reason_text, reason_code in reasons:
        keyboard.add(InlineKeyboardButton(reason_text, callback_data=f'help_reason_{reason_code}'))
    
    keyboard.add(InlineKeyboardButton('🔙 Отмена', callback_data='help_cancel'))
    
    await callback.message.edit_text(
        "📝 <b>Выберите причину для обжалования блокировки:</b>\n\n"
        "Администратор рассмотрит вашу заявку в кратчайшие сроки.",
        reply_markup=keyboard
    )
    await callback.answer()

# Обработка выбора причины
@DP.callback_query_handler(lambda c: c.data.startswith('help_reason_'))
async def help_process_reason(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    reason_code = callback.data.replace('help_reason_', '')
    
    reason_texts = {
        'blocking_error': "Блокировка по ошибке",
        'too_long': "Слишком долгий срок блокировки",
        'explain_position': "Хочу объяснить свою позицию",
        'technical_issue': "Техническая проблема"
    }
    
    # Только готовые причины - сразу отправляем заявку
    reason = reason_texts.get(reason_code, "Не указана")
    await send_help_request(callback, user_id, chat_id, reason)
    await state.finish()

# Функция отправки заявки
async def send_help_request(callback: types.CallbackQuery, user_id: int, chat_id: int, reason: str):
    user_name = callback.from_user.full_name
    username = f"@{callback.from_user.username}" if callback.from_user.username else "нет username"
    
    # Получаем информацию о блокировке
    block_info = USERS.get_block_info(user_id, chat_id)
    block_reason = block_info['reason'] if block_info else "Нарушение правил"
    
    # Формируем текст заявки
    message_text = (
        f"🚫 <b>Заявка на рассмотрение блокировки</b>\n"
        f"👤 <b>Пользователь:</b> {user_name}\n"
        f"📱 <b>Username:</b> {username}\n"
        f"🆔 <b>ID:</b> {user_id}\n"
        f"💬 <b>Причина блокировки:</b> {block_reason}\n"
        f"📝 <b>Причина обжалования:</b> {reason}\n\n"
        f"<i>Пользователь не согласен с блокировкой и просит рассмотреть заявку.</i>"
    )
    
    # Сохраняем заявку в базу данных
    message_id = USERS.add_help_message(user_id, chat_id, message_text, reason)
    
    if message_id:
        await callback.answer("✅ Ваша заявка отправлена администратору!", show_alert=True)
        
        # Уведомляем всех админов
        for admin_id in ADMIN_IDS:
            try:
                await BOT.send_message(
                    admin_id,
                    message_text
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления админу {admin_id}: {e}")
    else:
        await callback.answer("❌ Ошибка при отправке заявки", show_alert=True)

# Отмена выбора причины
@DP.callback_query_handler(lambda c: c.data == 'help_cancel')
async def help_cancel(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❌ <b>Отправка заявки отменена</b>\n\n"
        "Если вы передумали, всегда можете воспользоваться командой /help снова."
    )
    await callback.answer()

# 🔥 ПРОСТАЯ АДМИН ПАНЕЛЬ (как в старой версии)
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
        InlineKeyboardButton('♻️ Сбросить рейтинги', callback_data='admin-reset-all'),
        InlineKeyboardButton('🏆 Сбросить соревнования', callback_data='admin-reset-competition')
    )
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='back-to-main'))

    await callback.message.edit_text(
        f"⚙️ <b>Панель администратора</b>\n\n"
        f"<i>Выберите действие:</i>",
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
        f"👥 <b>Выберите пользователя для блокировки:</b>",
        reply_markup=keyboard
    )
    await callback.answer()


# Выбор времени блокировки
@DP.callback_query_handler(lambda c: c.data.startswith('block_select_user-'))
async def admin_block_select_time(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split('-')[1])
    user_name = KNOWN_USERS.get(target_user_id, f"ID {target_user_id}")
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton('⏰ 15 минут', callback_data=f'block_confirm-{target_user_id}-15'),
        InlineKeyboardButton('⏰ 30 минут', callback_data=f'block_confirm-{target_user_id}-30')
    )
    keyboard.add(
        InlineKeyboardButton('⏰ 1 час', callback_data=f'block_confirm-{target_user_id}-60'),
        InlineKeyboardButton('⏰ 12 часов', callback_data=f'block_confirm-{target_user_id}-720')
    )
    keyboard.add(
        InlineKeyboardButton('⏰ 24 часа', callback_data=f'block_confirm-{target_user_id}-1440'),
        InlineKeyboardButton('🚫 Навсегда', callback_data=f'block_confirm-{target_user_id}-525600')
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
    target_user_id = int(data_parts[1])
    minutes = int(data_parts[2])
    user_name = KNOWN_USERS.get(target_user_id, f"ID {target_user_id}")
    
    # Предполагаем, что блокировка в основном чате
    chat_id = callback.message.chat.id
    
    # Блокируем пользователя
    if minutes == 525600:  # "Навсегда" - 1 год
        success = USERS.block_user(target_user_id, chat_id, "Нарушение правил", 525600)
        duration_text = "навсегда (1 год)"
    else:
        success = USERS.block_user(target_user_id, chat_id, "Нарушение правил", minutes)
        duration_text = f"{minutes} минут"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад в админку', callback_data='admin'))
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Пользователь заблокирован!</b>\n\n"
            f"👤 <b>Имя:</b> {user_name}\n"
            f"⏳ <b>Длительность:</b> {duration_text}",
            reply_markup=keyboard
        )
        
        # Уведомляем пользователя без указания ID
        try:
            if minutes == 525600:
                duration_message = "навсегда (1 год)"
            else:
                hours = minutes // 60
                mins = minutes % 60
                duration_message = f"{hours} часов {mins} минут" if hours > 0 else f"{minutes} минут"
            
            await BOT.send_message(
                target_user_id,
                f"🚫 <b>Вы были заблокированы в казино-боте!</b>\n\n"
                f"⏳ <b>Длительность:</b> {duration_message}\n\n"
                f"<i>Если вы считаете, что блокировка несправедлива, "
                f"используйте команду /help в чате, чтобы написать администратору.</i>"
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
    
    # Получаем список заблокированных пользователей в текущем чате
    chat_id = callback.message.chat.id
    blocked_users = USERS.get_all_blocked_users(chat_id)
    
    if not blocked_users:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
        
        await callback.message.edit_text(
            f"📭 <b>В этом чате нет заблокированных пользователей</b>",
            reply_markup=keyboard
        )
        await callback.answer()
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for user in blocked_users:
        user_id = user['user_id']
        user_name = KNOWN_USERS.get(user_id, "Пользователь")
        
        keyboard.add(InlineKeyboardButton(
            f'✅ {user_name}', 
            callback_data=f'unblock_user-{user_id}'
        ))
    
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    await callback.message.edit_text(
        f"✅ <b>Выберите пользователя для разблокировки:</b>",
        reply_markup=keyboard
    )
    await callback.answer()

# Выполнение разблокировки
@DP.callback_query_handler(lambda c: c.data.startswith('unblock_user-'))
async def admin_unblock_execute(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    target_user_id = int(callback.data.split('-')[1])
    user_name = KNOWN_USERS.get(target_user_id, "Пользователь")
    
    # Разблокируем пользователя во всех чатах (или в текущем)
    chat_id = callback.message.chat.id
    
    # Получаем все блокировки этого пользователя в текущем чате
    blocked_users = USERS.get_all_blocked_users(chat_id)
    user_blocked = any(user['user_id'] == target_user_id for user in blocked_users)
    
    if not user_blocked:
        await callback.answer("❌ Этот пользователь не заблокирован в этом чате", show_alert=True)
        return
    
    # Разблокируем пользователя
    success = USERS.unblock_user(target_user_id, chat_id)
    
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
                target_user_id,
                f"✅ <b>Вы были разблокированы!</b>\n\n"
                f"Администратор снял с вас блокировку. Теперь вы можете снова использовать бота."
            )
        except:
            pass
    
    await callback.answer()

@DP.callback_query_handler(lambda c: c.data == 'admin-reset-competition')
async def admin_reset_competition(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    # Сбрасываем только статистику соревнований
    success = USERS.reset_competition_stats()

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Статистика соревнований успешно сброшена!</b>\n\n"
            f"Все очки и рейтинги для соревнований обнулены. Теперь можно начать новый турнир.",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка при сбросе статистики соревнований</b>\n\n"
            f"Попробуйте позже или проверьте логи.",
            reply_markup=keyboard
        )
    
    await callback.answer()

# 🔥 ИСПРАВЛЕННЫЙ ОБРАБОТЧИК НАЗАД
@DP.callback_query_handler(lambda c: c.data == 'back-to-main')
async def back_to_main(callback: types.CallbackQuery):
    # Используем прямой вызов функции main_menu
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    # Создаем фейковое сообщение с правильной структурой
    class FakeMessage:
        def __init__(self, user_id, chat_id, user_full_name):
            self.from_user = type('obj', (object,), {
                'id': user_id,
                'full_name': user_full_name,
                'username': None
            })()
            self.chat = type('obj', (object,), {
                'id': chat_id
            })()
            self.text = '/start'
            self.message_thread_id = None
    
    user_full_name = callback.from_user.full_name
    fake_message = FakeMessage(user_id, chat_id, user_full_name)
    
    await main_menu(fake_message)
    await callback.answer()

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
    
    text_lines = [f"<b>Ваши текущие серии побед:</b>\n"]
    
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
    
    text_lines.append(f"\n<i>Удачи в установлении новых рекордов!</i>")
    
    await BOT.send_message(
        message.chat.id,
        '\n'.join(text_lines),
        message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None
    )

if __name__ == '__main__':
    # Инициализируем обработчики
    messages_handler = MessagesHandler(DP, BOT, GAMES, USERS)
    rating_handler = RatingHandler(DP, BOT, USERS)
    
    print("🤖 Бот запущен и работает...")
    print("Для остановки нажми Ctrl+C")
    
    executor.start_polling(DP, skip_updates=False, allowed_updates=["message", "callback_query"])
