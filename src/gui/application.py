import os
import os.path
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Notify", "0.7")
from gi.repository import GLib, Gio, Gtk, Notify

from .main_window import MainWindow
from bluetooth_scanner import BluetoothScanner
from datastore import Datastore


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="me.rehack.agua_amiga",
                         flags=Gio.ApplicationFlags.FLAGS_NONE, **kwargs)
        self.window = None
        self.scanner = BluetoothScanner()

        data_path = GLib.get_user_data_dir() + '/agua_amiga/'

        if not os.path.exists(data_path):
            os.mkdir(data_path)

        database_name = "water.db"
        self.datastore = Datastore(data_path + database_name)

        Notify.init("Agua Amiga")
        self.notification = Notify.Notification()

        self.connect('shutdown', self.on_quit)
        


    def update_device_list(self):
        devices = self.scanner.get_devices()
        if self.window is not None:
            self.window.list_devices.foreach(lambda child: child.destroy())
            for _, dev in devices.items():
                self.window.list_devices.add(Gtk.Label(label=dev.name))

            self.window.list_devices.show_all()

            while len(self.scanner.sip_stream):
                sip = self.scanner.sip_stream.pop()
                self.datastore.save_sip(*sip)

            self.window.update_goal_progress_bar()

        return True  # so this method keeps getting called from the timeout

    def do_activate(self):
        self.window = self.window or MainWindow(application=self, datastore=self.datastore)
        self.window.ensure_goal_set()
        self.window.update_goal_progress_bar()
        self.scanner.start_scanner()


        one_hour = 60 * 60
        GLib.timeout_add_seconds(5, self.update_device_list)
        GLib.timeout_add_seconds(timedelta(hours=1).seconds, self.remind_to_drink)


        self.window.present()



    def on_quit(self, widget):
        self.scanner.stop_scanner()


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
