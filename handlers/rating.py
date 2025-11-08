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
