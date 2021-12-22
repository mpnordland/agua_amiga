agua_amiga.spec:
	poetry run pyi-makespec agua_amiga/__init__.py --name agua_amiga --add-data "ui_definitions/*.glade:ui_definitions" --add-data "*.css:." --windowed

bundle: agua_amiga.spec
	poetry run pyinstaller agua_amiga.spec

package:
	poetry build


clean:
	- rm -r ./build
	- rm -r ./dist
	- rm *.spec
	- rm *.glade~