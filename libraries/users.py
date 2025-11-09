import time

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
            self.cur.execute("COMMIT")
        except Exception as e: 
            raise UserError(e)

    def reset_chat(self, chat_id: int):
        try:
            self.cur.execute("BEGIN")
            self.cur.execute("DELETE FROM tries WHERE chat_id = ?", (chat_id,))
            self.cur.execute("DELETE FROM wins WHERE chat_id = ?", (chat_id,))
            self.cur.execute("DELETE FROM jackpots WHERE chat_id = ?", (chat_id,))
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
            self.cur.execute("COMMIT")
            self.database.conn.commit()
            return True
        except Exception as e:
            print(f"Error resetting all stats: {e}")
            return False

    # Удаляем старый метод reset_period_stats
    # def reset_period_stats(self, period: str):
    #     ...

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
            # Получаем текущее значение
            self.cur.execute(
                f"SELECT {parameter} FROM {table} WHERE id = ? AND chat_id = ?",
                (id, chat_id)
            )
            result = self.cur.fetchone()
            
            current_value = result[0] if result and result[0] is not None else 0
            
            # Обновляем запись
            self.cur.execute(
                f"INSERT OR REPLACE INTO {table} (id, chat_id, {parameter}, timestamp) VALUES (?, ?, ?, ?)",
                (id, chat_id, current_value + 1, int(time.time()))
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
