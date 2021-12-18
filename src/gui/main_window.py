from .dialogs import AddWaterDialog, PreferencesDialog
from gi.repository import GLib, Gio, Gtk
from datetime import datetime
from datastore import Datastore, convert_from_display_to_mL, convert_from_mL_to_display
from .streak_window import StreakWindow


@Gtk.Template.from_file("MainWindow.glade")
class MainWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "MainWindow"

    button_add_water: Gtk.Button = Gtk.Template.Child()
    button_display_streak: Gtk.Button = Gtk.Template.Child()
    list_devices: Gtk.ListBox = Gtk.Template.Child()
    progress_daily_goal: Gtk.ProgressBar = Gtk.Template.Child()

    def __init__(self, *args, **kwargs) -> None:
        assert 'datastore' in kwargs.keys()
        self.datastore: Datastore = kwargs['datastore']
        del kwargs['datastore']

        super().__init__(*args, **kwargs)

        self.streak_window = None
    @Gtk.Template.Callback()
    def button_add_water_clicked_cb(self, widget, **_kwargs):
        assert self.button_add_water == widget
        display_units = self.datastore.get_display_units()
        dialog = AddWaterDialog(units=display_units)

        response = dialog.run()

        if response == Gtk.ResponseType.APPLY:
            volume = dialog.get_water_volume()
            if volume > 0 and self.datastore is not None:
                self.datastore.save_sip(volume, datetime.now(), "manual")

        dialog.destroy()

    @Gtk.Template.Callback()
    def button_preferences_clicked_cb(self, widget, **_kwargs):
        self.show_preferences_dialog()

    def streak_window_destroy_cb(self, widget, **_kwargs):
        self.button_display_streak.set_sensitive(True)


    @Gtk.Template.Callback()
    def button_display_streak_clicked_cb(self, widget, **_kwargs):
            self.button_display_streak.set_sensitive(False)
            streak_window = StreakWindow(datastore = self.datastore)
            streak_window.connect('destroy', self.streak_window_destroy_cb)
            streak_window.show()

    def show_preferences_dialog(self):
        display_units = self.datastore.get_display_units()
        dialog = PreferencesDialog(units=display_units, goal_volume=convert_from_mL_to_display(
            self.datastore.get_daily_goal_volume(), display_units))
        response = dialog.run()

        if response == Gtk.ResponseType.APPLY and self.datastore is not None:
            display_units = dialog.get_display_units()
            self.datastore.set_display_units(display_units)
            self.datastore.set_daily_goal_volume(
                convert_from_display_to_mL(dialog.get_goal_volume(), display_units))


        dialog.destroy()

    def ensure_goal_set(self):
        if self.datastore.get_daily_goal_volume() == 0:
            self.show_preferences_dialog()

    def update_goal_progress_bar(self):
        vol_drank_today = self.datastore.get_volume_drunk_today()
        goal_volume = self.datastore.get_daily_goal_volume()
        display_units = self.datastore.get_display_units()
        self.progress_daily_goal.set_fraction(convert_from_mL_to_display(vol_drank_today / goal_volume, display_units))
        self.progress_daily_goal.set_text(
            f"{convert_from_mL_to_display(vol_drank_today, display_units):.2f} of {convert_from_mL_to_display(goal_volume, display_units):.2f} {display_units.value}")
