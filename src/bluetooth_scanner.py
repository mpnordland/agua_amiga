from datetime import timedelta, datetime
from collections import deque
from gi.repository import GLib, Gio
from pydbus import SystemBus, Variant

import BLE_GATT


class BluetoothNotSupported(Exception):
    pass


class BluetoothScanner:

    def __init__(self) -> None:
        self.interfaces_added_subscription = None
        self.interfaces_removed_subscription = None
        self.sip_stream = deque()
        self.devices = {}

        try:
            self.system_bus = SystemBus()
            self.bluez = self.system_bus.get('org.bluez', '/')

            self.adapter = None
            for path, child in self.bluez.GetManagedObjects().items():
                if 'org.bluez.Adapter1' in child.keys():
                    self.adapter = self.system_bus.get('org.bluez', path)

                else:
                    self._interface_added_listener(path, child)

        except Exception as e:
            print(e)
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
        
        if self.interfaces_removed_subscription is not None:
            self.interfaces_removed_subscription.disconnect()

        for device in self.devices.values():
            device.cleanup()

    def get_devices(self):
        return self.devices

    def _interface_added_listener(self, path, interfaces):

        if 'org.bluez.Device1' in interfaces.keys() and not interfaces['org.bluez.Device1']['Blocked'] and interfaces['org.bluez.Device1']['Alias'] in ['h2o10C28']:
            self.devices[path] = WaterBottle(interfaces['org.bluez.Device1'], self.sip_stream)

    def _interface_removed_listener(self, path, interfaces):
        if path in self.devices.keys() and 'org.bluez.Device1' in interfaces:
            self.devices[path].cleanup()
            del self.devices[path]


class WaterBottle:
    """
    right now contains logic for Hidrate Spark 3
    probably need to do lots of abstraction/generalizing
    to work with other water bottles, which I don't have or know about existing.
    """
    BOTTLE_SIZE = 592
    SIPS_CHARACTERISTIC_UUID = '016e11b1-6c8a-4074-9e5a-076053f93784'

    def __init__(self, device_info, sip_stream) -> None:
        """
        connect to device, find correct characteristic, read value, parse it,
        setup notifications then read sips
        """
        self.sip_stream = sip_stream

        self.name = device_info['Alias']
        self.device = BLE_GATT.Central(device_info['Address'])
        self.device.connect()
        self.device.on_value_change(self.SIPS_CHARACTERISTIC_UUID, self.sips_notification_handler)
        value = self.device.char_read(self.SIPS_CHARACTERISTIC_UUID)
        SipSize, total, secondsAgo, no_sips_left_on_device = self.parseSip(value)

        if no_sips_left_on_device > 0:
            self.device.char_write(self.SIPS_CHARACTERISTIC_UUID, bytes.fromhex("57"))

    def sips_notification_handler(self, value):
        SipSize, total, secondsAgo, no_sips_left_on_device = self.parseSip(value)
        if SipSize > 0:
            self.sip_stream.appendleft((SipSize, datetime.now() - timedelta(milliseconds=secondsAgo), "waterbottle"))

        if no_sips_left_on_device > 0:
            self.device.char_write(self.SIPS_CHARACTERISTIC_UUID, bytes.fromhex("57"))



    def parseSip(self, data):
        """
        parses sips from data sent by water bottle.
        code taken from https://github.com/choonkiatlee/wban-python/commit/3c644a32702f2a37e7a9c10f49bc5ebfcbf0a688#diff-de5804e048e763f99ae84940f91d80e11b58f1b69da346d32a17abd6940e7db4R85
        """
        # Parsed from dataPointCharacteristicDidUpdate in RxBLEConnectCoordinator.java
        no_sips_left_on_device = data[0]
        b2 = data[1] & 255          # Likely some version of sip size as percentage of bottle fullness

        SipSize = (self.BOTTLE_SIZE * b2) / 100

        # This bit of list comprehension magic gets us [data[3], data[2]]
        total = int.from_bytes(data[3:1:-1], "little") & 65535

        secondsAgo = int.from_bytes(data[8:4:-1], "little") & -1

        # print("Sip Size: {0}, Total: {1}, Seconds Ago: {2}, Sips Left: {3}".format(
        #     SipSize, total, secondsAgo, no_sips_left_on_device))

        return SipSize, total, secondsAgo, no_sips_left_on_device


    def cleanup(self):
        self.device.remove_notify(self.SIPS_CHARACTERISTIC_UUID)
        self.device.disconnect()