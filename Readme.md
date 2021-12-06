# Summary
In the vein of hydro homies, I have dubbed this project "Agua Amiga".
I've got 6 features planned:
- Track and display water intake towards a daily goal
- Track and display streaks (so many days hit goal, maybe just drank water at all)
- Save water data to a file somewhere in an easy to analyze format
- Preferences dialog to set goal and units that should be used
- Collect sip data from Hidrate Spark 3 water bottles
- Allow adding water drank from non smart containers


# Data model

Note about units: the UI ill allow using either mL or oz. The program will always use mL in the data. It will convert
to oz when needed to display information.

Goals: a list of daily goals. Most recent row is current goal. End time of goal is implied by start time of next goal.
 - volume (always uses mL)
 - time started

Drinks: a list of water intakes.

- volume (always uses mL)
- time (time of entry for manual water entry, time of drink for smart water bottles)
- source