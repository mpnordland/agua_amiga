# running this file should run the app
import sys
from gui.application import Application

application = Application()

try:
    application.run(sys.argv)
except KeyboardInterrupt:
    application.on_quit()