import time
import datetime

class UserError(Exception):
    pass

class UserNotFound(Exception):
    pass

class Users:
    def __init__(self, database):
        self.database = database
        self.cur = self.database.db

        # Создаем таблицы с новой структурой
        self.cur.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT, 
                congratulate BOOL
            );

            CREATE TABLE IF NOT EXISTS tries (
                id INTEGER,
                chat_id INTEGER,
                slots INTEGER DEFAULT 0,
                dice INTEGER DEFAULT 0, 
                dart INTEGER DEFAULT 0,
                bask INTEGER DEFAULT 0,
                foot INTEGER DEFAULT 0,
                bowl INTEGER DEFAULT 0,
                timestamp INTEGER,
                PRIMARY KEY (id, chat_id)
            );

            CREATE TABLE IF NOT EXISTS wins (
                id INTEGER,
                chat_id INTEGER,
                slots INTEGER DEFAULT 0,
                dice INTEGER DEFAULT 0,
                dart INTEGER DEFAULT 0,
                bask INTEGER DEFAULT 0,
                foot INTEGER DEFAULT 0,
                bowl INTEGER DEFAULT 0,
                timestamp INTEGER,
                PRIMARY KEY (id, chat_id)
            );

            CREATE TABLE IF NOT EXISTS jackpots (
                id INTEGER,
                chat_id INTEGER,
                slots INTEGER DEFAULT 0,
                timestamp INTEGER,
                PRIMARY KEY (id, chat_id)
            );

            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER,
                chat_id INTEGER,
                game_type TEXT,
                tries INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                jackpots INTEGER DEFAULT 0,
                date TEXT,
                PRIMARY KEY (id, chat_id, game_type, date)
            );
            
            CREATE TABLE IF NOT EXISTS weekly_stats (
                id INTEGER,
                chat_id INTEGER,
                game_type TEXT,
                tries INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                jackpots INTEGER DEFAULT 0,
                week_start TEXT,
                PRIMARY KEY (id, chat_id, game_type, week_start)
            );

            CREATE TABLE IF NOT EXISTS win_streaks (
                id INTEGER,
                chat_id INTEGER,
                game_type TEXT,
                current_streak INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0,
                last_win_timestamp INTEGER,
                PRIMARY KEY (id, chat_id, game_type)
            );
        ''')
        self.database.conn.commit()

    def add(self, id: int, name: str):
        try:
            self.cur.execute("BEGIN")
            self.cur.execute("INSERT OR IGNORE INTO users (id, name, congratulate) VALUES (?, ?, ?)", (id, name, True))
            self.cur.execute("COMMIT")
        except Exception as e: 
            raise UserError(e)

    def add_admin(self, user_id: int):
        try:
            self.cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
            self.database.conn.commit()
        except Exception as e: 
            raise UserError(e)

    def is_admin(self, user_id: int) -> bool:
        try:
            self.cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            return self.cur.fetchone() is not None
        except Exception as e: 
            raise UserError(e)

    def reset_user(self, id: int, chat_id: int):
        try:
            self.cur.execute("BEGIN")
            self.cur.execute("DELETE FROM tries WHERE id = ? AND chat_id = ?", (id, chat_id))
            self.cur.execute("DELETE FROM wins WHERE id = ? AND chat_id = ?", (id, chat_id))
            self.cur.execute("DELETE FROM jackpots WHERE id = ? AND chat_id = ?", (id, chat_id))
            self.cur.execute("DELETE FROM win_streaks WHERE id = ? AND chat_id = ?", (id, chat_id))
            self.cur.execute("COMMIT")
        except Exception as e: 
            raise UserError(e)

    def reset_chat(self, chat_id: int):
        try:
            self.cur.execute("BEGIN")
            self.cur.execute("DELETE FROM tries WHERE chat_id = ?", (chat_id,))
            self.cur.execute("DELETE FROM wins WHERE chat_id = ?", (chat_id,))
            self.cur.execute("DELETE FROM jackpots WHERE chat_id = ?", (chat_id,))
            self.cur.execute("DELETE FROM win_streaks WHERE chat_id = ?", (chat_id,))
            self.cur.execute("COMMIT")
        except Exception as e: 
            raise UserError(e)

    def reset_all_stats(self):
        """Сбрасывает всю статистику"""
        try:
            self.cur.execute("BEGIN")
            self.cur.execute("DELETE FROM tries")
            self.cur.execute("DELETE FROM wins")
            self.cur.execute("DELETE FROM jackpots")
            self.cur.execute("DELETE FROM daily_stats")
            self.cur.execute("DELETE FROM weekly_stats")
            self.cur.execute("DELETE FROM win_streaks")
            self.cur.execute("COMMIT")
            self.database.conn.commit()
            return True
        except Exception as e:
            print(f"Error resetting all stats: {e}")
            return False

    def get_current_date(self):
        """Возвращает текущую дату в формате YYYY-MM-DD"""
        return datetime.datetime.now().strftime("%Y-%m-%d")

    def get_current_week_start(self):
        """Возвращает дату начала текущей недели (понедельник)"""
        today = datetime.datetime.now().date()
        start_of_week = today - datetime.timedelta(days=today.weekday())
        return start_of_week.strftime("%Y-%m-%d")

    def update_win_streak(self, user_id: int, chat_id: int, game_type: str, is_win: bool):
        """Обновляет серию выигрышей для пользователя"""
        try:
            # Получаем текущую серию
            self.cur.execute(
                "SELECT current_streak, best_streak FROM win_streaks WHERE id = ? AND chat_id = ? AND game_type = ?",
                (user_id, chat_id, game_type)
            )
            result = self.cur.fetchone()
            
            current_streak = 0
            best_streak = 0
            
            if result:
                current_streak = result[0] or 0
                best_streak = result[1] or 0
            
            if is_win:
                # Увеличиваем текущую серию
                current_streak += 1
                # Обновляем лучшую серию если текущая больше
                if current_streak > best_streak:
                    best_streak = current_streak
            else:
                # Сбрасываем текущую серию при проигрыше
                current_streak = 0
            
            # Сохраняем или обновляем запись
            self.cur.execute('''
                INSERT OR REPLACE INTO win_streaks 
                (id, chat_id, game_type, current_streak, best_streak, last_win_timestamp) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, chat_id, game_type, current_streak, best_streak, int(time.time()) if is_win else None))
            
            self.database.conn.commit()
            return current_streak, best_streak
        except Exception as e:
            print(f"Error updating win streak: {e}")
            return 0, 0

    def get_win_streaks(self, chat_id: int, game_type: str = None):
        """Получает серии выигрышей для чата"""
        try:
            if game_type:
                self.cur.execute('''
                    SELECT id, game_type, current_streak, best_streak 
                    FROM win_streaks 
                    WHERE chat_id = ? AND game_type = ? AND current_streak > 0
                    ORDER BY current_streak DESC
                ''', (chat_id, game_type))
            else:
                self.cur.execute('''
                    SELECT id, game_type, current_streak, best_streak 
                    FROM win_streaks 
                    WHERE chat_id = ? AND current_streak > 0
                    ORDER BY current_streak DESC
                ''', (chat_id,))
            
            results = []
            for row in self.cur.fetchall():
                results.append({
                    'id': row[0],
                    'game_type': row[1],
                    'current_streak': row[2] or 0,
                    'best_streak': row[3] or 0
                })
            return results
        except Exception as e:
            print(f"Error getting win streaks: {e}")
            return []

    def increment_period_stats(self, user_id: int, chat_id: int, game_type: str, tries: int = 0, wins: int = 0, jackpots: int = 0):
        """Увеличивает статистику для текущих дня и недели"""
        try:
            current_date = self.get_current_date()
            week_start = self.get_current_week_start()
            
            # Обновляем дневную статистику
            self.cur.execute('''
                INSERT INTO daily_stats (id, chat_id, game_type, tries, wins, jackpots, date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id, chat_id, game_type, date) 
                DO UPDATE SET 
                    tries = daily_stats.tries + excluded.tries,
                    wins = daily_stats.wins + excluded.wins,
                    jackpots = daily_stats.jackpots + excluded.jackpots
            ''', (user_id, chat_id, game_type, tries, wins, jackpots, current_date))
            
            # Обновляем недельную статистику
            self.cur.execute('''
                INSERT INTO weekly_stats (id, chat_id, game_type, tries, wins, jackpots, week_start)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id, chat_id, game_type, week_start) 
                DO UPDATE SET 
                    tries = weekly_stats.tries + excluded.tries,
                    wins = weekly_stats.wins + excluded.wins,
                    jackpots = weekly_stats.jackpots + excluded.jackpots
            ''', (user_id, chat_id, game_type, tries, wins, jackpots, week_start))
            
            self.database.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating period stats: {e}")
            return False

    def get_daily_stats(self, chat_id: int, date: str = None):
        """Получает дневную статистику"""
        if date is None:
            date = self.get_current_date()
        
        try:
            self.cur.execute('''
                SELECT id, game_type, tries, wins, jackpots 
                FROM daily_stats 
                WHERE chat_id = ? AND date = ?
            ''', (chat_id, date))
            
            results = []
            for row in self.cur.fetchall():
                results.append({
                    'id': row[0],
                    'game_type': row[1],
                    'tries': row[2] or 0,
                    'wins': row[3] or 0,
                    'jackpots': row[4] or 0
                })
            return results
        except Exception as e:
            print(f"Error getting daily stats: {e}")
            return []

    def get_weekly_stats(self, chat_id: int, week_start: str = None):
        """Получает недельную статистику"""
        if week_start is None:
            week_start = self.get_current_week_start()
        
        try:
            self.cur.execute('''
                SELECT id, game_type, tries, wins, jackpots 
                FROM weekly_stats 
                WHERE chat_id = ? AND week_start = ?
            ''', (chat_id, week_start))
            
            results = []
            for row in self.cur.fetchall():
                results.append({
                    'id': row[0],
                    'game_type': row[1],
                    'tries': row[2] or 0,
                    'wins': row[3] or 0,
                    'jackpots': row[4] or 0
                })
            return results
        except Exception as e:
            print(f"Error getting weekly stats: {e}")
            return []

    def get(self, table: str, id: int, chat_id: int = None):
        try:
            if chat_id is not None:
                self.cur.execute(f"SELECT * FROM {table} WHERE id = ? AND chat_id = ?", (id, chat_id))
            else:
                self.cur.execute(f"SELECT * FROM {table} WHERE id = ?", (id,))
            
            columns = [description[0] for description in self.cur.description]
            result = self.cur.fetchone()
            if result:
                data = dict(zip(columns, result))
                # Заменяем None на 0 для числовых полей
                for key in list(data.keys()):
                    if key not in ['id', 'chat_id', 'name', 'congratulate', 'timestamp'] and data[key] is None:
                        data[key] = 0
                return data
            return None
        except Exception as e: 
            # Если таблица не существует, возвращаем None
            if "no such table" in str(e):
                return None
            raise UserError(e)

    def set(self, table: str, id: int, chat_id: int, parameter: str, value):
        try:
            if table == 'users':
                self.cur.execute(
                    f"UPDATE {table} SET {parameter} = ? WHERE id = ?",
                    (value, id)
                )
            else:
                self.cur.execute(
                    f"INSERT OR REPLACE INTO {table} (id, chat_id, {parameter}, timestamp) VALUES (?, ?, ?, ?)",
                    (id, chat_id, value, int(time.time()))
                )
            self.database.conn.commit()
        except Exception as e: 
            raise UserError(e)

    def increment(self, table: str, id: int, chat_id: int, parameter: str):
        try:
            # Сначала получаем текущую запись целиком
            self.cur.execute(
                f"SELECT * FROM {table} WHERE id = ? AND chat_id = ?",
                (id, chat_id)
            )
            result = self.cur.fetchone()
            
            if result:
                # Если запись существует, обновляем только нужное поле
                columns = [description[0] for description in self.cur.description]
                current_data = dict(zip(columns, result))
                
                # Увеличиваем только нужный параметр, остальные сохраняем
                current_value = current_data.get(parameter, 0) or 0
                updated_value = current_value + 1
                current_data[parameter] = updated_value
                current_data['timestamp'] = int(time.time())
                
                # Создаем запрос INSERT OR REPLACE со всеми полями
                if table == 'tries':
                    self.cur.execute(
                        "INSERT OR REPLACE INTO tries (id, chat_id, slots, dice, dart, bask, foot, bowl, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (id, chat_id, 
                         current_data.get('slots', 0), 
                         current_data.get('dice', 0),
                         current_data.get('dart', 0),
                         current_data.get('bask', 0),
                         current_data.get('foot', 0),
                         current_data.get('bowl', 0),
                         current_data['timestamp'])
                    )
                elif table == 'wins':
                    self.cur.execute(
                        "INSERT OR REPLACE INTO wins (id, chat_id, slots, dice, dart, bask, foot, bowl, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (id, chat_id,
                         current_data.get('slots', 0),
                         current_data.get('dice', 0),
                         current_data.get('dart', 0),
                         current_data.get('bask', 0),
                         current_data.get('foot', 0),
                         current_data.get('bowl', 0),
                         current_data['timestamp'])
                    )
                elif table == 'jackpots':
                    self.cur.execute(
                        "INSERT OR REPLACE INTO jackpots (id, chat_id, slots, timestamp) VALUES (?, ?, ?, ?)",
                        (id, chat_id, current_data.get('slots', 0), current_data['timestamp'])
                    )
            else:
                # Если записи нет, создаем новую запись со всеми полями
                if table == 'tries':
                    base_values = {'slots': 0, 'dice': 0, 'dart': 0, 'bask': 0, 'foot': 0, 'bowl': 0}
                    base_values[parameter] = 1
                    self.cur.execute(
                        "INSERT INTO tries (id, chat_id, slots, dice, dart, bask, foot, bowl, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (id, chat_id,
                         base_values['slots'],
                         base_values['dice'],
                         base_values['dart'],
                         base_values['bask'],
                         base_values['foot'],
                         base_values['bowl'],
                         int(time.time()))
                    )
                elif table == 'wins':
                    base_values = {'slots': 0, 'dice': 0, 'dart': 0, 'bask': 0, 'foot': 0, 'bowl': 0}
                    base_values[parameter] = 1
                    self.cur.execute(
                        "INSERT INTO wins (id, chat_id, slots, dice, dart, bask, foot, bowl, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (id, chat_id,
                         base_values['slots'],
                         base_values['dice'],
                         base_values['dart'],
                         base_values['bask'],
                         base_values['foot'],
                         base_values['bowl'],
                         int(time.time()))
                    )
                elif table == 'jackpots':
                    self.cur.execute(
                        "INSERT INTO jackpots (id, chat_id, slots, timestamp) VALUES (?, ?, ?, ?)",
                        (id, chat_id, 1 if parameter == 'slots' else 0, int(time.time()))
                    )
            
            self.database.conn.commit()
        except Exception as e: 
            raise UserError(e)

    def get_all(self, table: str, chat_id: int = None):
        try:
            if chat_id is not None:
                self.cur.execute(f"SELECT * FROM {table} WHERE chat_id = ?", (chat_id,))
            else:
                self.cur.execute(f"SELECT * FROM {table}")
            
            columns = [description[0] for description in self.cur.description]
            results = []
            for row in self.cur.fetchall():
                data = dict(zip(columns, row))
                # Заменяем None на 0 для числовых полей
                for key in list(data.keys()):
                    if key not in ['id', 'chat_id', 'name', 'congratulate', 'timestamp'] and data[key] is None:
                        data[key] = 0
                results.append(data)
            return results
        except Exception as e: 
            if "no such table" in str(e):
                return []
            raise UserError(e)

    def get_time_filtered(self, table: str, chat_id: int, time_filter: str):
        """time_filter: 'day' или 'week'"""
        try:
            time_threshold = int(time.time()) - (86400 if time_filter == 'day' else 604800)
            
            self.cur.execute(f"SELECT * FROM {table} WHERE chat_id = ? AND timestamp >= ?", (chat_id, time_threshold))
            columns = [description[0] for description in self.cur.description]
            results = []
            for row in self.cur.fetchall():
                data = dict(zip(columns, row))
                # Заменяем None на 0 для числовых полей
                for key in list(data.keys()):
                    if key not in ['id', 'chat_id', 'name', 'congratulate', 'timestamp'] and data[key] is None:
                        data[key] = 0
                results.append(data)
            return results
        except Exception as e: 
            if "no such table" in str(e):
                return []
            raise UserError(e)

