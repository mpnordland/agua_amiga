import sqlite3
from enum import Enum
from datetime import datetime, timedelta


class Unit(Enum):
    FL_OZ = 'fl oz'
    ML = 'mL'


class Datastore:
    """
    Stores water data in a sqlite db
    """

    def __init__(self, db_path) -> None:
        self.connection = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.cursor = self.connection.cursor()

        self.ensure_database_tables_exist()

    def get_display_units(self) -> Unit:
        self.cursor.execute("Select value from settings where name = 'display_units'")
        row = self.cursor.fetchone()

        if row:
            return Unit(row[0])

        return Unit.ML

    def set_display_units(self, units: Unit):
        self.cursor.execute('''INSERT INTO settings (name, value)
                            VALUES('display_units', :units) ON CONFLICT DO UPDATE SET value=excluded.value''', {'units': units.value})
        self.connection.commit()

    def save_sip(self, volume, time, source):
        self.cursor.execute('''INSERT INTO drinks (volume, time, source)
                            VALUES(:volume, :time, :source)''', {'volume': volume, 'source': source, 'time': time})
        self.connection.commit()

    def get_daily_goal_volume(self):
        self.cursor.execute('''SELECT volume FROM goals ORDER BY time DESC''')
        row = self.cursor.fetchone()

        if row:
            return row[0]

        return 0

    def set_daily_goal_volume(self, volume):
        self.cursor.execute('''INSERT INTO goals (volume, time) VALUES(:volume, :time)''',
                            {'volume': volume, 'time': datetime.now()})
        self.connection.commit()

    def get_volume_drunk_today(self):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.cursor.execute('''SELECT SUM(volume) FROM drinks WHERE datetime(time) >= datetime(:day_start) AND datetime(time) < datetime(:day_end)''',
                            {'day_start': today, 'day_end': today + timedelta(days=1)})

        row = self.cursor.fetchone()

        if row and row[0] is not None:
            return row[0]

        return 0

    def ensure_database_tables_exist(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS settings (name text primary key, value text)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS goals (volume real, time timestamp)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS drinks (volume real, time timestamp, source text)''')
        self.connection.commit()


# we use mL internally and convert to fluid ounces if they are chosen.
# see the Readme.md file
# conversion factor retrieved from https://en.wikipedia.org/wiki/Fluid_ounce on 2021-0-12-17T17:38
ML_IN_ONE_OZ = 29.57353


def convert_from_mL_to_display(volume_in_mL, display_unit: Unit):
    if display_unit == Unit.FL_OZ:
        return volume_in_mL / ML_IN_ONE_OZ
    else:
        return volume_in_mL


def convert_from_display_to_mL(display_volume, display_unit: Unit):
    if display_unit == Unit.ML:
        return display_volume
    else:
        return display_volume * ML_IN_ONE_OZ
