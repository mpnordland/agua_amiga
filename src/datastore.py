import sqlite3
from datetime import datetime, timedelta


class Datastore:
    """
    store this in a sqlite db somehow maybe
    """

    def __init__(self, db_path) -> None:
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()

        self.ensure_database_tables_exist()

    def get_display_units(self) -> str:
        self.cursor.execute("Select value from settings where name = 'display_units'")
        return self.cursor.fetchone()[0]

    def set_display_units(self, units):
        self.cursor.execute('''INSERT INTO settings (name, value)
                            VALUES('display_units', :units)''', {'units': units})
        self.connection.commit()

    def save_sip(self, volume, source, time):
        self.cursor.execute('''INSERT INTO drinks (volume, time, source)
                            VALUES(:volume, :time, :source)''', {'volume': volume, 'source': source, 'time': time})
        self.connection.commit()

    def get_daily_goal_volume(self):
        self.cursor.execute('''SELECT volume FROM goals ORDER BY time''')
        return self.cursor.fetchone()[0]

    def set_daily_goal_volume(self, volume):
        self.cursor.execute('''INSERT INTO goals (volume, time) VALUES(:volume, :time)''',
                            {'volume': volume, 'time': datetime.now()})
        self.connection.commit()

    def get_volume_drunk_today(self):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.cursor.execute('''SELECT SUM(volume) FROM drinks WHERE time >= :day_start AND time < :day_end GROUP BY volume''',
                            {'day_start': today, 'day_end': today + timedelta(days=1)})
        return self.cursor.fetchone()[0]

    def ensure_database_tables_exist(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS settings (name text, value text)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS goals (volume real, time datetime)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS drinks (volume real, time datetime, source text)''')
        self.connection.commit()
