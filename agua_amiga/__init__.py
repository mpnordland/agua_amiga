# running this file should run the app
import sys
from agua_amiga.gui.application import Application

def run():
    application = Application()
    try:
        application.run(sys.argv)
    except KeyboardInterrupt:
        application.on_quit()


if __name__ == '__main__':
    run()