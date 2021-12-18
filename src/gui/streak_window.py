from gi.repository import GLib, Gio, Gtk
from datetime import datetime, timedelta, date
from datastore import Datastore, convert_from_display_to_mL, convert_from_mL_to_display


@Gtk.Template.from_file("StreakWindow.glade")
class StreakWindow(Gtk.Window):
    __gtype_name__ = "StreakWindow"


    calendar_streaks: Gtk.Button = Gtk.Template.Child()

    def __init__(self, *args, **kwargs) -> None:
        assert 'datastore' in kwargs.keys()
        self.datastore: Datastore = kwargs['datastore']
        del kwargs['datastore']

        super().__init__(*args, **kwargs)

        self.update_marked_days()



    def update_marked_days(self):
        self.calendar_streaks.clear_marks()
        month_start = date(self.calendar_streaks.get_property('year'), self.calendar_streaks.get_property('month') + 1, 1)
        if month_start.month < 12:
            month_end = month_start.replace(month=month_start.month + 1) - timedelta(days=1)
        else:
            month_end = date(month_start.year + 1, 1, 1)

        display_units = self.datastore.get_display_units()
        days = self.datastore.get_days_drunk_water(month_start, month_end)
        if days is not None:
            water_data = dict(days)
            for day in days:
                parsed_day = date.fromisoformat(day[0])
                self.calendar_streaks.mark_day(parsed_day.day)


            def detail_func(widget, year, month, day):
                try:
                    day_volume_drunk = water_data[f"{year}-{month+1:2}-{day:2}"]
                    return f"<span size=\"medium\" line_height=\"2\">{convert_from_mL_to_display(day_volume_drunk, display_units)} {display_units.value}</span>"
                except Exception as e:
                    return f"<span size=\"medium\" line_height=\"2\">0 {display_units.value}</span>"

            self.calendar_streaks.set_detail_func(detail_func)


    @Gtk.Template.Callback()
    def calendar_streaks_month_changed_cb(self, widget, **_kwargs):
        self.update_marked_days()