import json, os, time, logging
from datetime import datetime, timedelta

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
from aiogram.types import ContentType, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

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
ADMIN_IDS = [1773287874]  # Только вы как админ
for admin_id in ADMIN_IDS:
    USERS.add_admin(admin_id)

# Список чатов для уведомлений админов (можно добавить ID чатов)
ADMIN_CHAT_IDS = ADMIN_IDS  # Отправляем уведомления админам в личку

# 🔥 НОВЫЙ МИДЛВАРЬ ДЛЯ БЛОКИРОВКИ ПОЛЬЗОВАТЕЛЕЙ
class BlockedUsersMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        user_id = message.from_user.id
        chat_id = message.chat.id
        
        # Проверяем блокировку в базе данных
        if USERS.is_user_blocked(user_id, chat_id):
            logger.warning(f"🚫 БЛОКИРОВКА сообщения: UserID={user_id}, ChatID={chat_id}")
            
            # Для команд /start и /casino отправляем сообщение о блокировке
            if message.text and message.text.lower() in ['/start', '/casino']:
                block_info = USERS.get_block_info(user_id, chat_id)
                if block_info:
                    end_time = datetime.strptime(block_info['end'], '%Y-%m-%d %H:%M:%S')
                    remaining = end_time - datetime.now()
                    minutes_left = int(remaining.total_seconds() / 60)
                    
                    warning_msg = await BOT.send_message(
                        chat_id,
                        f'🚫 Пользователь @{message.from_user.username if message.from_user.username else message.from_user.full_name} заблокирован!\n'
                        f'⏰ <b>Причина:</b> {block_info["reason"]}\n'
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
        
        if USERS.is_user_blocked(user_id, chat_id):
            logger.warning(f"🚫 БЛОКИРОВКА callback: UserID={user_id}")
            await callback_query.answer("❌ Вы заблокированы в этом чате", show_alert=True)
            raise CancelHandler()

class UserRegistrationMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, data: dict):
        if not USERS.get('users', message.from_user.id):
            USERS.add(message.from_user.id, message.from_user.full_name)

# 🔥 РЕГИСТРИРУЕМ МИДЛВАРИ В ПРАВИЛЬНОМ ПОРЯДКЕ
DP.middleware.setup(BlockedUsersMiddleware())  # ПЕРВЫЙ - блокировка
DP.middleware.setup(UserRegistrationMiddleware())  # ВТОРОЙ - регистрация

# main menu handler
@DP.message_handler(commands=['casino', 'start'])
async def main_menu(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # 🔥 ЛОГИРУЕМ КОМАНДЫ /start И /casino
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

ℹ️ <b>Информация:</b> /info
🆘 <b>Помощь:</b> /help""",
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

# 🔥 НОВАЯ КОМАНДА /help
@DP.message_handler(commands=['help'])
async def help_command(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('📝 Написать сообщение'))
    keyboard.add(KeyboardButton('❌ Отмена'))
    
    await BOT.send_message(
        message.chat.id,
        "🆘 <b>Центр помощи</b>\n\n"
        "Если у вас возникли проблемы или вас заблокировали по ошибке, "
        "нажмите кнопку ниже, чтобы написать сообщение администраторам.\n\n"
        "<i>Администраторы ответят вам в ближайшее время.</i>",
        reply_markup=keyboard
    )

# Обработчик кнопок помощи
@DP.message_handler(lambda message: message.text == '📝 Написать сообщение')
async def write_help_message(message: types.Message):
    await BOT.send_message(
        message.chat.id,
        "✍️ <b>Напишите ваше сообщение:</b>\n\n"
        "<i>Опишите вашу проблему подробно. Администраторы увидят это сообщение.</i>",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Устанавливаем состояние для ожидания сообщения
    from aiogram.dispatcher import FSMContext
    from aiogram.dispatcher.filters.state import State, StatesGroup
    
    class HelpStates(StatesGroup):
        waiting_for_message = State()
    
    await HelpStates.waiting_for_message.set()

# Обработчик отмены
@DP.message_handler(lambda message: message.text == '❌ Отмена', state='*')
async def cancel_help(message: types.Message, state: FSMContext):
    await state.finish()
    await BOT.send_message(
        message.chat.id,
        "❌ <b>Отменено</b>",
        reply_markup=ReplyKeyboardRemove()
    )

# Обработчик текста помощи
@DP.message_handler(state='*', content_types=ContentType.TEXT)
async def process_help_message(message: types.Message, state: FSMContext):
    from aiogram.dispatcher.filters.state import State, StatesGroup
    
    class HelpStates(StatesGroup):
        waiting_for_message = State()
    
    if await state.get_state() == HelpStates.waiting_for_message.state:
        user_id = message.from_user.id
        chat_id = message.chat.id
        user_name = message.from_user.full_name
        username = f"@{message.from_user.username}" if message.from_user.username else "нет username"
        
        # Сохраняем сообщение в базе данных
        message_id = USERS.add_help_message(user_id, chat_id, message.text)
        
        if message_id:
            # Отправляем уведомление админам
            for admin_id in ADMIN_CHAT_IDS:
                try:
                    await BOT.send_message(
                        admin_id,
                        f"🆘 <b>НОВОЕ СООБЩЕНИЕ ПОМОЩИ</b>\n\n"
                        f"👤 <b>Пользователь:</b> {user_name}\n"
                        f"🔗 <b>Username:</b> {username}\n"
                        f"🆔 <b>ID:</b> {user_id}\n"
                        f"💬 <b>Сообщение ID:</b> {message_id}\n\n"
                        f"📝 <b>Текст:</b>\n{message.text}\n\n"
                        f"📌 <b>Действия:</b>\n"
                        f"/unblock_{user_id}_{chat_id} - разблокировать\n"
                        f"/viewhelp_{message_id} - просмотреть детали"
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
            
            await BOT.send_message(
                chat_id,
                "✅ <b>Сообщение отправлено!</b>\n\n"
                "Администраторы получили ваше сообщение и ответят в ближайшее время.\n\n"
                "<i>Спасибо за обращение!</i>",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await BOT.send_message(
                chat_id,
                "❌ <b>Ошибка!</b>\n\n"
                "Не удалось отправить сообщение. Попробуйте позже.",
                reply_markup=ReplyKeyboardRemove()
            )
        
        await state.finish()

# 🔥 ОБНОВЛЕННАЯ АДМИН ПАНЕЛЬ
@DP.callback_query_handler(lambda c: c.data == 'admin')
async def admin_panel(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton('♻️ Сбросить ВСЕ рейтинги', callback_data='admin-reset-all'),
        InlineKeyboardButton('👥 Заблокированные', callback_data='admin-blocked-list')
    )
    keyboard.add(
        InlineKeyboardButton('📊 Статистика блоков', callback_data='admin-block-stats'),
        InlineKeyboardButton('🆘 Сообщения помощи', callback_data='admin-help-messages')
    )
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='back-to-main'))

    await callback.message.edit_text(
        "⚙️ <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()

# Список заблокированных пользователей
@DP.callback_query_handler(lambda c: c.data == 'admin-blocked-list')
async def admin_blocked_list(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    blocked_users = USERS.get_all_blocked_users()
    
    if not blocked_users:
        text = "📭 <b>Нет заблокированных пользователей</b>"
    else:
        text = "🚫 <b>Заблокированные пользователи:</b>\n\n"
        for i, user in enumerate(blocked_users, 1):
            from datetime import datetime
            end_time = datetime.strptime(user['end'], '%Y-%m-%d %H:%M:%S')
            remaining = end_time - datetime.now()
            minutes_left = max(0, int(remaining.total_seconds() / 60))
            
            text += f"{i}. <b>ID:</b> {user['user_id']}\n"
            text += f"   <b>Причина:</b> {user['reason']}\n"
            text += f"   <b>Осталось:</b> {minutes_left} мин\n"
            text += f"   <b>Действие:</b> /unblock_{user['user_id']}_{user['chat_id']}\n\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Статистика блоков
@DP.callback_query_handler(lambda c: c.data == 'admin-block-stats')
async def admin_block_stats(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    # Можно добавить статистику блоков
    blocked_users = USERS.get_all_blocked_users()
    total_blocks = len(blocked_users)
    
    text = f"📊 <b>Статистика блокировок</b>\n\n"
    text += f"🔒 <b>Всего заблокировано:</b> {total_blocks} пользователей\n\n"
    
    if blocked_users:
        text += "<b>Активные блокировки:</b>\n"
        for user in blocked_users[:10]:  # Показываем первые 10
            from datetime import datetime
            end_time = datetime.strptime(user['end'], '%Y-%m-%d %H:%M:%S')
            remaining = end_time - datetime.now()
            minutes_left = max(0, int(remaining.total_seconds() / 60))
            
            text += f"• ID {user['user_id']}: {user['reason']} ({minutes_left} мин осталось)\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Сообщения помощи
@DP.callback_query_handler(lambda c: c.data == 'admin-help-messages')
async def admin_help_messages(callback: types.CallbackQuery):
    if not USERS.is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора", show_alert=True)
        return
    
    help_messages = USERS.get_pending_help_messages()
    
    if not help_messages:
        text = "📭 <b>Нет новых сообщений помощи</b>"
    else:
        text = f"🆘 <b>Сообщения помощи ({len(help_messages)}):</b>\n\n"
        for i, msg in enumerate(help_messages, 1):
            text += f"{i}. <b>ID сообщения:</b> {msg['message_id']}\n"
            text += f"   <b>Пользователь:</b> ID {msg['user_id']}\n"
            text += f"   <b>Действие:</b> /viewhelp_{msg['message_id']}\n\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='admin'))
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Команда для разблокировки пользователя
@DP.message_handler(lambda message: message.text and message.text.startswith('/unblock_'))
async def unblock_user_command(message: types.Message):
    if not USERS.is_admin(message.from_user.id):
        return
    
    try:
        parts = message.text.split('_')
        if len(parts) == 3:
            user_id = int(parts[1])
            chat_id = int(parts[2])
            
            success = USERS.unblock_user(user_id, chat_id)
            
            if success:
                await message.reply(f"✅ Пользователь {user_id} разблокирован в чате {chat_id}")
                
                # Уведомляем пользователя
                try:
                    await BOT.send_message(
                        user_id,
                        "✅ <b>Вы были разблокированы!</b>\n\n"
                        "Администратор снял с вас блокировку. Теперь вы можете снова использовать бота."
                    )
                except:
                    pass  # Пользователь мог заблокировать бота
            else:
                await message.reply(f"❌ Не удалось разблокировать пользователя {user_id}")
    except ValueError:
        await message.reply("❌ Неверный формат команды. Используйте: /unblock_userId_chatId")

# Команда для просмотра сообщения помощи
@DP.message_handler(lambda message: message.text and message.text.startswith('/viewhelp_'))
async def view_help_message_command(message: types.Message):
    if not USERS.is_admin(message.from_user.id):
        return
    
    try:
        message_id = int(message.text.split('_')[1])
        
        # Получаем все сообщения и ищем нужное
        help_messages = USERS.get_pending_help_messages()
        target_msg = None
        
        for msg in help_messages:
            if msg['message_id'] == message_id:
                target_msg = msg
                break
        
        if target_msg:
            # Получаем информацию о пользователе
            user_info = USERS.get('users', target_msg['user_id'])
            user_name = user_info['name'] if user_info else "Неизвестно"
            
            text = f"📋 <b>Сообщение помощи #{message_id}</b>\n\n"
            text += f"👤 <b>Пользователь:</b> {user_name}\n"
            text += f"🆔 <b>ID:</b> {target_msg['user_id']}\n"
            text += f"💬 <b>Чат:</b> {target_msg['chat_id']}\n"
            text += f"🕒 <b>Время:</b> {target_msg['timestamp']}\n\n"
            text += f"📝 <b>Текст сообщения:</b>\n{target_msg['message_text']}\n\n"
            text += f"📌 <b>Действия:</b>\n"
            text += f"/unblock_{target_msg['user_id']}_{target_msg['chat_id']} - разблокировать\n"
            text += f"/closehelp_{message_id} - закрыть обращение"
            
            await message.reply(text)
            
            # Помечаем как просмотренное
            USERS.update_help_message_status(message_id, 'viewed')
        else:
            await message.reply("❌ Сообщение не найдено или уже обработано")
    except (ValueError, IndexError):
        await message.reply("❌ Неверный формат команды. Используйте: /viewhelp_messageId")

# Команда для закрытия обращения
@DP.message_handler(lambda message: message.text and message.text.startswith('/closehelp_'))
async def close_help_message_command(message: types.Message):
    if not USERS.is_admin(message.from_user.id):
        return
    
    try:
        message_id = int(message.text.split('_')[1])
        
        success = USERS.update_help_message_status(message_id, 'closed')
        
        if success:
            await message.reply(f"✅ Обращение #{message_id} закрыто")
        else:
            await message.reply(f"❌ Не удалось закрыть обращение #{message_id}")
    except (ValueError, IndexError):
        await message.reply("❌ Неверный формат команды. Используйте: /closehelp_messageId")

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
    # Создаем сообщение для вызова main_menu
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

# Команда для проверки статуса блокировки
@DP.message_handler(commands=['mystatus'])
async def my_status(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if USERS.is_user_blocked(user_id, chat_id):
        block_info = USERS.get_block_info(user_id, chat_id)
        if block_info:
            from datetime import datetime
            end_time = datetime.strptime(block_info['end'], '%Y-%m-%d %H:%M:%S')
            remaining = end_time - datetime.now()
            minutes_left = max(0, int(remaining.total_seconds() / 60))
            
            text = f"🚫 <b>Вы заблокированы!</b>\n\n"
            text += f"⏰ <b>Причина:</b> {block_info['reason']}\n"
            text += f"⏳ <b>Разблокировка через:</b> {minutes_left} минут\n\n"
            text += f"Если это ошибка, используйте команду /help"
    else:
        warnings_fast = USERS.get_warnings_count(user_id, chat_id, 'fast_deps')
        
        text = f"✅ <b>Статус: Активен</b>\n\n"
        text += f"⚠️ <b>Предупреждения (быстрые депы):</b> {warnings_fast}/5\n\n"
        
        if warnings_fast > 0:
            text += f"<i>При {5 - warnings_fast} нарушениях будете заблокированы</i>"
    
    await BOT.send_message(
        message.chat.id,
        text,
        message_thread_id=message.message_thread_id if hasattr(message, 'message_thread_id') else None
    )

if __name__ == '__main__':
    MessagesHandler(DP, BOT, GAMES, USERS)
    RatingHandler(DP, BOT, USERS)

    print("🤖 Бот запущен и работает...")
    print("Для остановки нажми Ctrl+C")
    
    executor.start_polling(DP, skip_updates=False, allowed_updates=["message", "callback_query"])
