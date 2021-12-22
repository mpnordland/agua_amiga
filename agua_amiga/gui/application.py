from datetime import datetime, timedelta
import os
import os.path
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")
from gi.repository import GLib, Gio, Gtk, Notify, Gdk

from .main_window import MainWindow
from agua_amiga.bluetooth_scanner import BluetoothNotSupported, BluetoothScanner, BluetoothStatus
from agua_amiga.datastore import Datastore

class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="me.rehack.agua_amiga",
                         flags=Gio.ApplicationFlags.FLAGS_NONE, **kwargs)
        self.window = None
        self.scanner = BluetoothScanner(self.bluetooth_status_update, self.devices_update)

        data_path = GLib.get_user_data_dir() + '/agua_amiga/'

        if not os.path.exists(data_path):
            os.mkdir(data_path)

        database_name = "water.db"
        self.datastore = Datastore(data_path + database_name)

        Notify.init("Agua Amiga")
        self.notification = Notify.Notification()

        self.connect('shutdown', self.on_quit)

        style_provider = Gtk.CssProvider()
        style_provider.load_from_path("styles.css")

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def update(self):
        if self.window and self.scanner:
            have_updates = len(self.scanner.sip_stream)

            while len(self.scanner.sip_stream):
                sip = self.scanner.sip_stream.pop()
                self.datastore.save_sip(*sip)

            if have_updates:
                self.window.update_goal_progress_bar()

        return True  # so this method keeps getting called from the timeout

    def do_activate(self):
        self.window = self.window or MainWindow(application=self, datastore=self.datastore)
        self.window.ensure_goal_set()
        self.window.update_goal_progress_bar()
        self.scanner.start_scanner()

        GLib.timeout_add_seconds(5, self.update)
        GLib.timeout_add_seconds(timedelta(hours=1).seconds, self.remind_to_drink)

        self.window.present()

    def on_quit(self, widget=None):
        self.scanner.close()

    def remind_to_drink(self):
        volume_drunk = self.datastore.get_volume_drunk_today()
        goal_volume = self.datastore.get_daily_goal_volume()

        # want to notify user if not keeping up with their goal
        # say a sliding window where they get a notification if
        # the percentage of the day completed is 10 percentage points
        # greater than the percentage of the goal drank

        # define the day as starting at 09:00 and ending at 21:00

        hours_in_day = 12
        start_hour = 6
        end_hour = start_hour + hours_in_day
        current_time = datetime.now()

        day_percentage = (current_time - timedelta(hours=start_hour)).hour / hours_in_day
        goal_percentage = volume_drunk / goal_volume

        if volume_drunk < goal_volume and day_percentage > goal_percentage:
            self.notification.update("Hey, you should drink some water!",
                                     f"You have drunk {goal_percentage:.2%} of your goal for today.")
            self.notification.show()
        else:
            self.notification.close()

        return True

    def bluetooth_status_update(self, status: BluetoothStatus, data):
        if self.window is None:
            return False

        if status == BluetoothStatus.ENABLED:
            self.window.mark_bluetooth_enabled()
        elif status == BluetoothStatus.DISABLED:
            self.window.mark_bluetooth_disabled()

        else:
            self.scanner.stop_scanner()
            self.window.mark_bluetooth_error()

    def devices_update(self, devices):
        if self.window:
            self.window.update_device_list([dev.name for dev in devices.values()])
