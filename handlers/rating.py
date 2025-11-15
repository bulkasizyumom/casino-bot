from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from libraries.users import Users

class RatingHandler:
    def __init__(self, dp: Dispatcher, bot: Bot, database: Users):
        self.database = database
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
            
            # Добавляем кнопку для серий выигрышей
            keyboard.add(InlineKeyboardButton('🔥 Серии выигрышей', callback_data=f'rating_criteria-{game}-{period}-streaks'))
            
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
                'jackpots': 'Джекпоты',
                'streaks': 'Серии выигрышей'
            }
            
            emoji = game_emojis.get(game, '🎰')
            game_name = game_names.get(game, 'Слоты')
            period_name = period_names.get(period, 'сутки')
            criteria_name = criteria_names.get(criteria, 'Выигрыши')

            # Получаем рейтинг
            if criteria == 'streaks':
                rating_data = self.build_streak_rating(callback.message.chat.id, game, period)
            else:
                rating_data = self.build_period_rating(callback.message.chat.id, game, criteria, period)
            
            user_place = self.find_user_place(callback.from_user.id, rating_data)

            # Формируем текст рейтинга
            if not rating_data:
                rating_text = "📊 <i>Пока нет статистики для этого периода</i>"
            else:
                rating_lines = []
                for i, (user_data, value) in enumerate(rating_data[:10]):  # Топ-10
                    if criteria == 'winrate':
                        value_text = f"{value:.1%}"
                    elif criteria == 'streaks':
                        value_text = f"{int(value)} 🔥"
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

    def build_period_rating(self, chat_id: int, game: str, criteria: str, period: str):
        """Строит рейтинг из системы периодов"""
        ranking = []
        user_names = {}

        # Получаем имена пользователей
        all_users = self.database.get_all('users')
        for user in all_users:
            user_names[user['id']] = user.get('name', 'Unknown')

        # Получаем статистику за период
        if period == 'day':
            stats_data = self.database.get_daily_stats(chat_id)
        else:  # week
            stats_data = self.database.get_weekly_stats(chat_id)

        # Группируем статистику по пользователям
        user_stats = {}
        for stat in stats_data:
            if stat['game_type'] == game:
                user_id = stat['id']
                if user_id not in user_stats:
                    user_stats[user_id] = {
                        'tries': 0,
                        'wins': 0,
                        'jackpots': 0,
                        'best_streak': 0
                    }
                
                user_stats[user_id]['tries'] += stat['tries']
                user_stats[user_id]['wins'] += stat['wins']
                user_stats[user_id]['jackpots'] += stat['jackpots']
                # Для серий берем максимальное значение
                user_stats[user_id]['best_streak'] = max(user_stats[user_id]['best_streak'], stat['best_streak'])

        # Формируем рейтинг
        for user_id, stats in user_stats.items():
            if criteria == 'wins':
                value = stats['wins']
            elif criteria == 'tries':
                value = stats['tries']
            elif criteria == 'jackpots':
                value = stats['jackpots']
            elif criteria == 'winrate':
                value = stats['wins'] / stats['tries'] if stats['tries'] > 0 else 0
            elif criteria == 'streaks':
                value = stats['best_streak']
            else:
                value = 0
