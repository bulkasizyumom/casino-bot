from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from libraries.users import Users

class RatingHandler:
    def __init__(self, dp: Dispatcher, bot: Bot, database: Users):
        self.register(dp, bot, database)
    
    def register(self, dp: Dispatcher, bot: Bot, database: Users):
        # Главное меню рейтингов
        @dp.callback_query_handler(lambda c: c.data == 'rating_main')
        async def rating_main(callback: types.CallbackQuery):
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton('🎰 Слоты', callback_data='rating_game-slots'),
                InlineKeyboardButton('🎲 Кубик', callback_data='rating_game-dice')
            )
            keyboard.add(
                InlineKeyboardButton('⚽ Футбол', callback_data='rating_game-foot'),
                InlineKeyboardButton('🎳 Боулинг', callback_data='rating_game-bowl')
            )
            keyboard.add(
                InlineKeyboardButton('🏀 Баскетбол', callback_data='rating_game-bask'),
                InlineKeyboardButton('🎯 Дартс', callback_data='rating_game-dart')
            )
            keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='back-to-main'))

            await callback.message.edit_text(
                "🏆 <b>Рейтинги</b>\n\nВыберите игру:",
                reply_markup=keyboard
            )
            await callback.answer()

        # Выбор игры
        @dp.callback_query_handler(lambda c: c.data.startswith('rating_game-'))
        async def rating_select_game(callback: types.CallbackQuery):
            game = callback.data.split('-')[1]
            
            game_emojis = {
                'slots': '🎰',
                'dice': '🎲', 
                'foot': '⚽',
                'bowl': '🎳',
                'bask': '🏀',
                'dart': '🎯'
            }
            
            game_names = {
                'slots': 'Слоты',
                'dice': 'Кубик',
                'foot': 'Футбол', 
                'bowl': 'Боулинг',
                'bask': 'Баскетбол',
                'dart': 'Дартс'
            }
            
            emoji = game_emojis.get(game, '🎰')
            name = game_names.get(game, 'Слоты')

            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton('📅 За сутки', callback_data=f'rating_period-{game}-day'),
                InlineKeyboardButton('📅 За неделю', callback_data=f'rating_period-{game}-week')
            )
            keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data='rating_main'))

            await callback.message.edit_text(
                f"{emoji} <b>Рейтинги {name}</b>\n\nВыберите период:",
                reply_markup=keyboard
            )
            await callback.answer()

        # Выбор периода
        @dp.callback_query_handler(lambda c: c.data.startswith('rating_period-'))
        async def rating_select_period(callback: types.CallbackQuery):
            data_parts = callback.data.split('-')
            game = data_parts[1]
            period = data_parts[2]
            
            game_emojis = {
                'slots': '🎰',
                'dice': '🎲',
                'foot': '⚽',
                'bowl': '🎳', 
                'bask': '🏀',
                'dart': '🎯'
            }
            
            game_names = {
                'slots': 'Слоты',
                'dice': 'Кубик',
                'foot': 'Футбол',
                'bowl': 'Боулинг',
                'bask': 'Баскетбол', 
                'dart': 'Дартс'
            }
            
            period_names = {
                'day': 'сутки',
                'week': 'неделю'
            }
            
            emoji = game_emojis.get(game, '🎰')
            name = game_names.get(game, 'Слоты')
            period_name = period_names.get(period, 'сутки')

            keyboard = InlineKeyboardMarkup()
            
            # Для всех игр показываем стандартные кнопки
            keyboard.add(
                InlineKeyboardButton('✅ Выигрыши', callback_data=f'rating_criteria-{game}-{period}-wins'),
                InlineKeyboardButton('🎯 Попытки', callback_data=f'rating_criteria-{game}-{period}-tries')
            )
            keyboard.add(InlineKeyboardButton('📊 Винрейт', callback_data=f'rating_criteria-{game}-{period}-winrate'))
            
            # Только для слотов добавляем джекпоты
            if game == 'slots':
                keyboard.add(InlineKeyboardButton('⭐ Джекпоты', callback_data=f'rating_criteria-{game}-{period}-jackpots'))
            
            keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data=f'rating_game-{game}'))

            await callback.message.edit_text(
                f"{emoji} <b>Рейтинги {name}</b>\n📅 <b>Период:</b> за {period_name}\n\nВыберите критерий:",
                reply_markup=keyboard
            )
            await callback.answer()

        # Отображение рейтинга
        @dp.callback_query_handler(lambda c: c.data.startswith('rating_criteria-'))
        async def rating_show(callback: types.CallbackQuery):
            data_parts = callback.data.split('-')
            game = data_parts[1]
            period = data_parts[2]
            criteria = data_parts[3]
            
            game_emojis = {
                'slots': '🎰',
                'dice': '🎲',
                'foot': '⚽',
                'bowl': '🎳',
                'bask': '🏀',
                'dart': '🎯'
            }
            
            game_names = {
                'slots': 'Слоты',
                'dice': 'Кубик', 
                'foot': 'Футбол',
                'bowl': 'Боулинг',
                'bask': 'Баскетбол',
                'dart': 'Дартс'
            }
            
            period_names = {
                'day': 'сутки',
                'week': 'неделю'
            }
            
            criteria_names = {
                'wins': 'Выигрыши',
                'tries': 'Попытки',
                'winrate': 'Винрейт',
                'jackpots': 'Джекпоты'
            }
            
            emoji = game_emojis.get(game, '🎰')
            game_name = game_names.get(game, 'Слоты')
            period_name = period_names.get(period, 'сутки')
            criteria_name = criteria_names.get(criteria, 'Выигрыши')

            # Получаем рейтинг
            rating_data = build_rating(callback.message.chat.id, game, criteria, period)
            user_place = find_user_place(callback.from_user.id, rating_data)

            # Формируем текст рейтинга
            if not rating_data:
                rating_text = "📊 <i>Пока нет статистики для этого периода</i>"
            else:
                rating_lines = []
                for i, (user_data, value) in enumerate(rating_data[:10]):  # Топ-10
                    if criteria == 'winrate':
                        value_text = f"{value:.1%}"
                    else:
                        value_text = str(int(value))
                    
                    rating_lines.append(f"<b>{i+1}.</b> {user_data['name']} - {value_text}")
                
                rating_text = '\n'.join(rating_lines)

            title = f"{emoji} <b>РЕЙТИНГ {game_name.upper()}</b>"
            period_info = f"📅 <b>Период:</b> за {period_name}"
            criteria_info = f"📊 <b>Критерий:</b> {criteria_name}"
            user_info = f"👤 <b>Ваше место:</b> {user_place}"

            text = f"{title}\n{period_info}\n{criteria_info}\n{user_info}\n\n{rating_text}"

            # Клавиатура для возврата
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton('🔙 Назад', callback_data=f'rating_period-{game}-{period}'))

            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()

        def build_rating(chat_id: int, game: str, criteria: str, time_filter: str = None):
            """Строит рейтинг для конкретной игры и критерия"""
            ranking = []
            user_names = {}

            # Получаем имена пользователей
            all_users = database.get_all('users')
            for user in all_users:
                user_names[user['id']] = user.get('name', 'Unknown')

            if time_filter:
                # Для временных фильтров
                if criteria == 'wins':
                    users_data = database.get_time_filtered('wins', chat_id, time_filter)
                elif criteria == 'tries':
                    users_data = database.get_time_filtered('tries', chat_id, time_filter)
                elif criteria == 'jackpots':
                    users_data = database.get_time_filtered('jackpots', chat_id, time_filter)
                else:  # winrate
                    users_data = database.get_time_filtered('tries', chat_id, time_filter)
            else:
                # Для общей статистики (если понадобится)
                if criteria == 'wins':
                    users_data = database.get_all('wins', chat_id)
                elif criteria == 'tries':
                    users_data = database.get_all('tries', chat_id)
                elif criteria == 'jackpots':
                    users_data = database.get_all('jackpots', chat_id)
                else:  # winrate
                    users_data = database.get_all('tries', chat_id)

            for user_data in users_data:
                user_id = user_data['id']
                
                # Получаем значение для конкретной игры
                if criteria == 'winrate':
                    # Для винрейта нужны и победы и попытки
                    if time_filter:
                        wins_data = database.get_time_filtered('wins', chat_id, time_filter)
                        user_wins_data = next((w for w in wins_data if w['id'] == user_id), {})
                        user_tries_data = next((t for t in users_data if t['id'] == user_id), {})
                    else:
                        user_wins_data = database.get('wins', user_id, chat_id) or {}
                        user_tries_data = database.get('tries', user_id, chat_id) or {}
                    
                    wins = user_wins_data.get(game, 0)
                    tries = user_tries_data.get(game, 0)
                    value = wins / tries if tries > 0 else 0
                    
                elif criteria == 'jackpots':
                    # Джекпоты только для слотов
                    value = user_data.get('slots', 0) if game == 'slots' else 0
                    
                else:
                    # Выигрыши или попытки для конкретной игры
                    value = user_data.get(game, 0)

                if value > 0:  # Показываем только тех, у кого есть статистика
                    ranking.append(({'id': user_id, 'name': user_names.get(user_id, 'Unknown')}, value))

            return sorted(ranking, key=lambda x: x[1], reverse=True)

        def find_user_place(user_id: int, ranking: list):
            """Находит место пользователя в рейтинге"""
            for index, (user, _) in enumerate(ranking, start=1):
                if user['id'] == user_id:
                    return index
            return '–'
