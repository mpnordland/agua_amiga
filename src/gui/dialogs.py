import gi

from datastore import Unit
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


@Gtk.Template.from_file("AddWaterDialog.glade")
class AddWaterDialog(Gtk.Dialog):
    __gtype_name__ = "AddWaterDialog"

    spin_button_add_water: Gtk.SpinButton = Gtk.Template.Child()
    label_units: Gtk.SpinButton = Gtk.Template.Child()


    def __init__(self, *args, **kwargs) -> None:
        if 'units' in kwargs.keys():
            units = kwargs['units']
            del kwargs['units']
        else:
            units = Unit.ML

        super().__init__(*args, **kwargs)

        self.label_units.set_label(units.value)

    def get_water_volume(self):
        return self.spin_button_add_water.get_value()


@Gtk.Template.from_file("Preferences.glade")
class PreferencesDialog(Gtk.Dialog):
    __gtype_name__ = "PreferencesDialog"

    spin_button_goal_volume: Gtk.SpinButton = Gtk.Template.Child()
    radio_display_units_oz: Gtk.RadioButton = Gtk.Template.Child()
    radio_display_units_ml: Gtk.RadioButton = Gtk.Template.Child()

    def __init__(self, *args, **kwargs) -> None:
        if 'units' in kwargs.keys():
            units = kwargs['units']
            del kwargs['units']
        else:
            units = Unit.ML

        if 'goal_volume' in kwargs.keys():
            goal_volume = kwargs['goal_volume']
            del kwargs['goal_volume']
        else:
            goal_volume = 0

        super().__init__(*args, **kwargs)

        self.radio_display_units_oz.set_active(False)
        self.radio_display_units_ml.set_active(False)

        if units == Unit.FL_OZ: 
            self.radio_display_units_oz.set_active(True)

        else:
            self.radio_display_units_ml.set_active(True)

        self.spin_button_goal_volume.set_value(goal_volume)


    def get_display_units(self) -> Unit:
        if self.radio_display_units_oz.get_active():
            return Unit.FL_OZ

        return Unit.ML

    def get_goal_volume(self):
        return self.spin_button_goal_volume.get_value()