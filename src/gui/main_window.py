import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio, Gtk
from .dialogs import AddWaterDialog, PreferencesDialog


@Gtk.Template.from_file("MainWindow.glade")
class MainWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "MainWindow"


    button_add_water: Gtk.Button = Gtk.Template.Child()

    @Gtk.Template.Callback()
    def button_add_water_clicked_cb(self, widget, **_kwargs):
        assert self.button_add_water == widget
        dialog =  AddWaterDialog()

        dialog.run()

        dialog.destroy()

    @Gtk.Template.Callback()
    def button_preferences_clicked_cb(self, widget, **_kwargs):
        dialog = PreferencesDialog()


        dialog.run()

        dialog.destroy()

