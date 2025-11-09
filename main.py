def reset_period_stats(self, period: str):
    """Сбрасывает статистику за указанный период (day/week)"""
    try:
        time_threshold = int(time.time()) - (86400 if period == 'day' else 604800)
        
        self.cur.execute("BEGIN")
        self.cur.execute("DELETE FROM tries WHERE timestamp < ?", (time_threshold,))
        self.cur.execute("DELETE FROM wins WHERE timestamp < ?", (time_threshold,))
        self.cur.execute("DELETE FROM jackpots WHERE timestamp < ?", (time_threshold,))
        self.cur.execute("COMMIT")
        self.database.conn.commit()
        return True
    except Exception as e:
        print(f"Error resetting period stats: {e}")
        return False
