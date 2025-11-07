import sqlite3
import time

class Database():
    def __init__(self, name: str = 'database.db'):
        self.conn = sqlite3.connect(name, timeout=10, check_same_thread=False)
        self.db = self.conn.cursor()