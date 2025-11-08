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


from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from libraries.users import Users

class RatingHandler:
    def __init__(self, dp: Dispatcher, bot: Bot, database: Users):
        self.register(dp, bot, database)
    
    def register(self, dp: Dispatcher, bot: Bot, database: Users):
        def build_rating(chat_id: int, key: str, time_filter: str = None):
            if time_filter:
                users_data = database.get_time_filtered('tries', chat_id, time_filter)
            else:
                users_data = database.get_all('tries', chat_id)
            
            ranking = []
            user_names = {}

            # Получаем имена пользователей
            all_users = database.get_all('users')
            for user in all_users:
                user_names[user['id']] = user.get('name', 'Unknown')

            for user_data in users_data:
                user_id = user_data['id']
                
                if time_filter:
                    # Для временных фильтров используем данные из tries/wins/jackpots
                    if key == 'winrate':
                        wins_data = database.get_time_filtered('wins', chat_id, time_filter)
                        user_wins = sum([sum([val for k, val in win.items() if k not in ['id', 'chat_id', 'timestamp']]) 
                                       for win in wins_data if win['id'] == user_id])
                        user_tries = sum([sum([val for k, val in try_item.items() if k not in ['id', 'chat_id', 'timestamp']]) 
                                        for try_item in users_data if try_item['id'] == user_id])
                        value = user_wins / user_tries if user_tries > 0 else 0
                    elif key == 'jackpots':
                        jackpots_data = database.get_time_filtered('jackpots', chat_id, time_filter)
                        value = sum([jackpot.get('slots', 0) for jackpot in jackpots_data if jackpot['id'] == user_id])
                    elif key == 'wins':  # ИСПРАВЛЕНИЕ: отдельная обработка для выигрышей
                        wins_data = database.get_time_filtered('wins', chat_id, time_filter)
                        value = sum([sum([val for k, val in win.items() if k not in ['id', 'chat_id', 'timestamp']]) 
                                   for win in wins_data if win['id'] == user_id])
                    else:
                        value = sum([val for k, val in user_data.items() if k not in ['id', 'chat_id', 'timestamp']])
                else:
                    # Для общей статистики
                    if key == 'winrate':
                        wins = database.get('wins', user_id, chat_id) or {}
                        tries = database.get('tries', user_id, chat_id) or {}
                        wins_sum = sum([val for k, val in wins.items() if k not in ['id', 'chat_id', 'timestamp']])
                        tries_sum = sum([val for k, val in tries.items() if k not in ['id', 'chat_id', 'timestamp']])
                        value = wins_sum / tries_sum if tries_sum > 0 else 0
                    elif key == 'jackpots':
                        jackpots = database.get('jackpots', user_id, chat_id) or {}
                        value = jackpots.get('slots', 0)
                    else:
                        table_data = database.get(key, user_id, chat_id) or {}
                        value = sum([val for k, val in table_data.items() if k not in ['id', 'chat_id', 'timestamp']])

                if value > 0:  # Показываем только тех, у кого есть статистика
                    ranking.append(({'id': user_id, 'name': user_names.get(user_id, 'Unknown')}, value))

            return sorted(ranking, key=lambda x: x[1], reverse=True)[:10]

        def find_user_place(user_id: int, ranking: list):
            for index, (user, _) in enumerate(ranking, start=1):
                if user['id'] == user_id:
                    return index
            return '–'

        @dp.callback_query_handler(lambda c: c.data == 'rating')
        async def rating_handler(callback: types.CallbackQuery):
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton('🎰 Выигрыши', callback_data='rating-wins-all'),
                InlineKeyboardButton('🎰 Попытки', callback_data='rating-tries-all')
            )
            keyboard.row(
                InlineKeyboardButton('🎰 Джекпоты', callback_data='rating-jackpots-all'),
                InlineKeyboardButton('🎰 Винрейт', callback_data='rating-winrate-all')
            )
            keyboard.row(
                InlineKeyboardButton('📅 За сутки', callback_data='rating-time-day'),
                InlineKeyboardButton('📅 За неделю', callback_data='rating-time-week')
            )

            await bot.send_message(
                callback.message.chat.id,
                "<b>Выберите категорию и период рейтинга:</b>",
                reply_markup=keyboard,
                message_thread_id=callback.message.message_thread_id
            )
            await callback.answer()

        @dp.callback_query_handler(lambda c: c.data.startswith('rating-'))
        async def rating_callback(callback: types.CallbackQuery):
            parts = callback.data.split('-')
            key = parts[1] if len(parts) > 1 else 'wins'
            time_filter = parts[2] if len(parts) > 2 else None

            time_titles = {
                'all': "🎰 <b>РЕЙТИНГ</b>",
                'day': "📅 <b>РЕЙТИНГ ЗА СУТКИ</b>",
                'week': "📅 <b>РЕЙТИНГ ЗА НЕДЕЛЮ</b>"
            }

            keys = {
                'wins': "ВЫИГРЫШИ",
                'tries': "ПОПЫТКИ", 
                'jackpots': "ДЖЕКПОТЫ",
                'winrate': "ВИНРЕЙТ"
            }

            title = f"{time_titles.get(time_filter, '🎰 <b>РЕЙТИНГ</b>')} ПО {keys.get(key, 'ВЫИГРЫШАМ')}"

            rating = build_rating(callback.message.chat.id, key, time_filter)
            place = find_user_place(callback.from_user.id, rating)
            
            if not rating:
                text = "📊 <i>Пока нет статистики для этого периода</i>"
            else:
                text = '\n'.join(
                    f"<b>{i+1}.</b> {user.get('name')} - {round(val, 2) if key == 'winrate' else int(val)}"
                    for i, (user, val) in enumerate(rating)
                )

            result = [
                f"{title}\n<i>Ваше место: {place}</i>\n\n{text}\n",
                "<b>Вернуться в главное меню - /casino</b>"
            ]

            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton('🎰 Выигрыши', callback_data='rating-wins-all'),
                InlineKeyboardButton('🎰 Попытки', callback_data='rating-tries-all')
            )
            keyboard.row(
                InlineKeyboardButton('🎰 Джекпоты', callback_data='rating-jackpots-all'),
                InlineKeyboardButton('🎰 Винрейт', callback_data='rating-winrate-all')
            )
            keyboard.row(
                InlineKeyboardButton('📅 За сутки', callback_data='rating-time-day'),
                InlineKeyboardButton('📅 За неделю', callback_data='rating-time-week')
            )

            await callback.message.edit_text(
                '\n'.join(result),
                reply_markup=keyboard,
            )
            await callback.answer()
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


