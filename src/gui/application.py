import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk
from .main_window import MainWindow


class Application(Gtk.Application):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, application_id="dev.monique.Gtk1",
                         flags=Gio.ApplicationFlags.FLAGS_NONE, **kwargs)
        self.window = None

    def do_activate(self):
        self.window = self.window or MainWindow(application=self)
        self.window.present()
