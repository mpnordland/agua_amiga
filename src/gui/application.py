import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk
from .main_window import MainWindow
from bluetooth_scanner import BluetoothScanner


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="me.rehack.agua_amiga",
                         flags=Gio.ApplicationFlags.FLAGS_NONE, **kwargs)
        self.window = None
        self.scanner = BluetoothScanner()

    def update_device_list(self):
        devices = self.scanner.get_devices()
        self.window.list_devices.foreach(lambda child: child.destroy())
        for _, dev in devices.items():
            self.window.list_devices.add(Gtk.Label(label=dev.name))

        self.window.list_devices.show_all()
        return True #Do this so this keeps getting called from the timeout

    def do_activate(self):
        self.window = self.window or MainWindow(application=self)
        self.scanner.start_scanner()


        GLib.timeout_add_seconds(5, self.update_device_list)


        self.window.present()
