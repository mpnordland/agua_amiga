import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk
from .main_window import MainWindow
from bluetooth_scanner import BluetoothScanner
from datastore import Datastore


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="me.rehack.agua_amiga",
                         flags=Gio.ApplicationFlags.FLAGS_NONE, **kwargs)
        self.window = None
        self.scanner = BluetoothScanner()

        # TODO: use real data stored on disk, put db in correct XDG folder
        self.datastore = Datastore("test.db")
        self.datastore.set_daily_goal_volume(2471.936) # 87oz in mL


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


        GLib.timeout_add_seconds(5, self.update_device_list)


        self.window.present()



    def on_quit(self, widget):
        self.scanner.stop_scanner()


