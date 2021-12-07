from types import NoneType
from gi.repository import GLib
from pydbus import SystemBus, Variant


class BluetoothNotSupported(Exception):
    pass


class BluetoothScanner:

    def __init__(self) -> None:
        self.interfaces_added_subscription = None
        self.interfaces_removed_subscription = None

        self.devices = {}

        try:
            self.system_bus = SystemBus()
            self.bluez = self.system_bus.get('org.bluez', '/')

            self.adapter = None
            for path, child in self.bluez.GetManagedObjects():
                if 'org.bluez.Adapter1' in child.keys():
                    self.adapter = self.system_bus.get('org.bluez', path)
                    break

        except Exception as e:
            raise BluetoothNotSupported("Unable to initialize Bluetooth scanning")

        if self.adapter is None:
            raise BluetoothNotSupported("Could not find Bluetooth adapter")

    def start_scanner(self):
        """
        maybe instead pass a callback and add entries to ui that way.
        start scanner in another thread probably
        https://ianharvey.github.io/bluepy-doc/scanner.html
        """

        self.interfaces_added_subscription = self.bluez.InterfacesAdded.connect(self._interface_added_listener)
        self.interfaces_removed_subscription = self.bluez.InterfacesRemoved.connect(self._interface_removed_listener)
        self.adapter.SetDiscoveryFilter({'Transport': Variant.new_string('le')})
        self.adapter.StartDiscovery()


    def stop_scanner(self):
        self.adapter.StopDiscovery()
        if self.interfaces_added_subscription is not None:
            self.interfaces_added_subscription.disconnect()

    def get_devices(self):
        return self.devices


    def _interface_added_listener(self, path, interfaces):
        if 'org.bluez.Device1' in interfaces.keys() and not interfaces['org.bluez.Device1']['Blocked'].value:
            self.devices[path] = interfaces

    def _interface_removed_listener(self, path, interfaces):
        if path in self.devices.keys() and 'org.bluez.Device1' in interfaces.keys():
            del self.devices[path]