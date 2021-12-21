from datetime import timedelta
import os
import os.path
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")
from gi.repository import GLib, Gio, Gtk, Notify, Gdk

from datastore import Datastore
from bluetooth_scanner import BluetoothNotSupported, BluetoothScanner
from .main_window import MainWindow

class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="me.rehack.agua_amiga",
                         flags=Gio.ApplicationFlags.FLAGS_NONE, **kwargs)
        self.window = None
        try:
            self.scanner = BluetoothScanner()
        except BluetoothNotSupported as e:
            self.scanner = None

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
        have_updates = False
        if self.window:
            if self.scanner and self.scanner.running():
                have_updates = len(self.scanner.sip_stream) > 0
                while len(self.scanner.sip_stream):
                    sip = self.scanner.sip_stream.pop()
                    self.datastore.save_sip(*sip)

                devices = self.scanner.get_devices()
                self.window.update_device_list([dev.name for dev in devices.values()])
            elif self.scanner and self.scanner.bluetooth_enabled():
                self.scanner.start_scanner()
                self.window.mark_bluetooth_enabled()
            elif self.scanner:
                self.scanner.stop_scanner()
                self.window.mark_bluetooth_disabled()

            if have_updates:
                self.window.update_goal_progress_bar()

        return True  # so this method keeps getting called from the timeout

    def do_activate(self):
        self.window = self.window or MainWindow(application=self, datastore=self.datastore)
        self.window.ensure_goal_set()
        self.window.update_goal_progress_bar()
        if self.scanner and self.scanner.bluetooth_enabled():
            self.scanner.start_scanner()
        elif self.scanner:
            self.window.mark_bluetooth_disabled()
        else:
            self.window.mark_bluetooth_error()

        GLib.timeout_add_seconds(5, self.update)
        GLib.timeout_add_seconds(timedelta(hours=1).seconds, self.remind_to_drink)

        self.window.present()

    def on_quit(self, widget):
        if self.window:
            self.window.hide()
        if self.scanner:
            self.scanner.close()

    def remind_to_drink(self):
        volume_drunk = self.datastore.get_volume_drunk_today()
        goal_volume = self.datastore.get_daily_goal_volume()

        if volume_drunk <= goal_volume:
            self.notification.update("Hey, you should drink some water!",
                                     f"You have drunk {volume_drunk / goal_volume:.2%} of your goal for today.")
            self.notification.show()
        else:
            self.notification.close()

        return True
