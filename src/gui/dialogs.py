import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


@Gtk.Template.from_file("AddWaterDialog.glade")
class AddWaterDialog(Gtk.Dialog):
    __gtype_name__ = "AddWaterDialog"



@Gtk.Template.from_file("Preferences.glade")
class PreferencesDialog(Gtk.Dialog):
    __gtype_name__ = "PreferencesDialog"