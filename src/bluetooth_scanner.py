from datetime import timedelta, datetime
from collections import deque, defaultdict
from sqlite3.dbapi2 import adapters
import time
import enum
from typing import Any, cast
from dbus_next.glib import MessageBus
from dbus_next import BusType, Variant, introspection
from promise import Promise
import traceback

from gi.repository import GLib, Gio

BLUEZ_BUS_NAME = 'org.bluez'

ADAPTER_IFACE = 'org.bluez.Adapter1'
DEVICE_IFACE = 'org.bluez.Device1'
CHARACTERISTIC_IFACE = 'org.bluez.GattCharacteristic1'
OBJ_MANAGER_IFACE = 'org.freedesktop.DBus.ObjectManager'
PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"


class BluetoothStatus(enum.Enum):
    ENABLED = 1
    DISABLED = 2
    ERROR = 3


def dbus_callback_promise(method, *args):
    def resolver(resolve, reject):

        def callback(result, error=None):
            if isinstance(error, Exception):
                reject(error)
            else:
                resolve(result)

        method(*args, callback)

    return Promise(resolver)


class BluetoothNotSupported(Exception):
    pass


class BluetoothScanner:

    def __init__(self, status_callback, devices_callback) -> None:
        self.sip_stream = deque()
        self.devices = {}

        self.status_callback = status_callback
        self.devices_callback = devices_callback

        self.traceback_printer = traceback_printer(self.__class__.__name__)

        # sometimes when the app is closed and then immediately restarted
        # bluez or DBus just disconnects immediately when we try to read out
        # the bluez objects. A retry after a short wait seems to address that.
        for attempt in range(1, 4):
            try:

                self.system_bus = MessageBus(bus_type=BusType.SYSTEM).connect_sync()
                self.bluez_promise = self._get_dbus_proxy_object(BLUEZ_BUS_NAME, '/')

                def get_bluez_child_objects(bluez):
                    obj_manager = bluez.get_interface(OBJ_MANAGER_IFACE)
                    return dbus_callback_promise(obj_manager.call_get_managed_objects) \
                        .then(lambda children: children[0])

                def find_adapter(children):
                    for path, child in children.items():
                        if ADAPTER_IFACE in child.keys():
                            return self._get_dbus_proxy_object(BLUEZ_BUS_NAME, path)

                    return Promise.reject(BluetoothNotSupported("Could not find Bluetooth adapter"))

                self.adapter_promise = self.bluez_promise.then(get_bluez_child_objects) \
                    .then(find_adapter, self._promise_error_handler)

            except Exception as e:
                if attempt < 3:
                    time.sleep(0.5)
                else:
                    self._send_status_update(BluetoothStatus.ERROR, BluetoothNotSupported(
                        "Unable to initialize Bluetooth scanning"))

    def start_scanner(self):
        """
        tells the bluetooth adaptor to start discovering BTLE devices
        and adds listeners for when new devices are found
        """

        def _start(obj_manager, adapter_proxy):
            obj_manager.on_interfaces_added(self._interface_added_listener)
            obj_manager.on_interfaces_removed(self._interface_removed_listener)
            adapter = adapter_proxy.get_interface(ADAPTER_IFACE)
            adapter_properties = adapter_proxy.get_interface(PROPERTIES_IFACE)

            adapter_properties.on_properties_changed(self._adapter_properties_listener)

            def _check_powered_on(powered):
                if powered:
                    self._start_adapter_discovering().catch(traceback_printer("start scanner check powered on"))
                    self._get_discovered_devices()
                    self._send_status_update(BluetoothStatus.ENABLED)
                else:
                    self._send_status_update(BluetoothStatus.DISABLED)

            dbus_callback_promise(adapter.get_powered).then(
                _check_powered_on, traceback_printer("start scanner get_powered"))

        Promise.all([
            self.bluez_promise.then(lambda bluez: bluez.get_interface(OBJ_MANAGER_IFACE)),
            self.adapter_promise
        ]).then(lambda args: _start(*args), self._promise_error_handler)

    def stop_scanner(self):
        """
        Stops the bluetooth adaptor finding new devices, removes device listeners
        and cleans up any existing devices
        """
        def _stop(obj_manager, adapter_proxy):

            obj_manager.off_interfaces_added(self._interface_added_listener)
            obj_manager.off_interfaces_removed(self._interface_removed_listener)

            for device in self.devices.values():
                device.cleanup()

            adapter = adapter_proxy.get_interface(ADAPTER_IFACE)
            adapter_properties = adapter_proxy.get_interface(PROPERTIES_IFACE)

            adapter_properties.off_properties_changed(self._adapter_properties_listener)
            dbus_callback_promise(adapter.call_stop_discovery)

            self._send_status_update(BluetoothStatus.DISABLED)

        return Promise.all([
            self._obj_manager_promise(),
            self.adapter_promise
        ]).then(lambda args: _stop(*args), self._promise_error_handler)

    def close(self):
        self.stop_scanner().then(lambda _: dbus_callback_promise(self.system_bus.disconnect))

    def _interface_added_listener(self, path, interfaces):
        if DEVICE_IFACE in interfaces.keys() and not interfaces[DEVICE_IFACE]['Blocked'].value and interfaces[DEVICE_IFACE]['Alias'].value in ['h2o10C28']:
            def create_water_bottle_and_notify(device, obj_manager):
                self.devices[path] = WaterBottle(interfaces[DEVICE_IFACE]['Alias'].value,
                                                 BtleDevice(path, device, obj_manager), self.sip_stream)
                self._send_devices_update()

            Promise.all([self._get_dbus_proxy_object(BLUEZ_BUS_NAME, path),
                         self._obj_manager_promise()]) \
                .then(lambda args: create_water_bottle_and_notify(*args), self._promise_error_handler)

    def _interface_removed_listener(self, path, interfaces):
        if path in self.devices.keys() and DEVICE_IFACE in interfaces:
            self.devices[path].cleanup()
            del self.devices[path]
            GLib.idle_add(self.devices_callback, self.devices)

    def _adapter_properties_listener(self, iface_name, props_changed, props_removed):
        if iface_name == ADAPTER_IFACE and "Powered" in props_changed:
            if props_changed["Powered"].value:
                self._start_adapter_discovering()
                self._send_status_update(BluetoothStatus.ENABLED)
                self._send_devices_update()
            else:
                self._send_status_update(BluetoothStatus.DISABLED)

    def _start_adapter_discovering(self):
        return self.adapter_promise.then(lambda adapter_proxy: adapter_proxy.get_interface(ADAPTER_IFACE)) \
            .then(lambda adapter: dbus_callback_promise(adapter.call_set_discovery_filter, {'Transport': Variant('s', 'le')})
                  .then(lambda _: dbus_callback_promise(adapter.call_start_discovery))) \
            .catch(traceback_printer("start adapter discovering")) \
            .catch(self._promise_error_handler)

    def _get_discovered_devices(self):
        return self._obj_manager_promise().then(lambda obj_manager:
                                                dbus_callback_promise(obj_manager.call_get_managed_objects)
                                                .then(lambda children: children[0])
                                                .then(
                                                    lambda children: [self._interface_added_listener(path, child) for path, child in children.items()],
                                                )).catch(traceback_printer("get discovered devices"))

    def _get_dbus_proxy_object(self, bus_name, path):
        return dbus_callback_promise(self.system_bus.introspect, bus_name, path).then(lambda introspection: self.system_bus.get_proxy_object(bus_name, path, introspection))

    def _promise_error_handler(self, error: Exception):
        traceback_printer("promise error handler")(error)
        self._send_status_update(BluetoothStatus.ERROR, error)

    def _send_status_update(self, status: BluetoothStatus, data: Any = None):
        def _idle_callback():
            self.status_callback(status, data)
            return False

        GLib.idle_add(_idle_callback)

    def _send_devices_update(self):
        GLib.idle_add(self.devices_callback, self.devices)

    def _obj_manager_promise(self):
        return self.bluez_promise.then(lambda bluez: bluez.get_interface(OBJ_MANAGER_IFACE))


class CharacteristicNotifyHandler:

    def __init__(self, func) -> None:
        self.func = func

    def __call__(self, iface_name, props_changed, props_removed) -> Any:
        if iface_name == CHARACTERISTIC_IFACE and 'Value' in props_changed:
            self.func(props_changed['Value'].value)


def print_and_return(*args):
    print(*args)

    return args if len(args) > 1 else args[0]


def traceback_printer(location):
    def _printer(error):
        print(location)
        traceback.print_exception(error)

    return _printer


class BtleDevice:
    def __init__(self, path, device_proxy, obj_manager) -> None:
        self.path = path
        self.device_interface = device_proxy.get_interface(DEVICE_IFACE)
        self.properties_interface = device_proxy.get_interface(PROPERTIES_IFACE)
        self.system_bus = device_proxy.bus
        self.obj_manager = obj_manager
        self.characteristics_promise = Promise.reject(Exception("Couldn't get device characteristics"))
        self.handlers = defaultdict(list)
        self.traceback_printer = traceback_printer(self.__class__.__name__)

    def connect(self):

        def _filter_characteristics(children):

            promises = {}

            for path, child in children.items():
                characteristic_uuid = child.get(CHARACTERISTIC_IFACE, {}).get('UUID')

                if path.startswith(self.path) and characteristic_uuid:
                    promises[characteristic_uuid.value] = self._get_dbus_proxy_object(BLUEZ_BUS_NAME, path)

            return Promise.for_dict(promises)

        def _get_characteristics():
            return dbus_callback_promise(self.obj_manager.call_get_managed_objects) \
                .then(lambda children: children[0]) \
                .then(_filter_characteristics)

        def _get_now_or_later(services_resolved):
            if services_resolved:
                return _get_characteristics()

            return Promise(_trigger_characteristic_collection)

        def _trigger_characteristic_collection(resolve, reject):

            def _collect_characteristics(iface_name, props_changed, props_removed):
                if iface_name == DEVICE_IFACE and "ServicesResolved" in props_changed.keys() and props_changed["ServicesResolved"].value:
                    self.properties_interface.off_properties_changed(_collect_characteristics)
                    _get_characteristics().then(resolve, reject)

            self.properties_interface.on_properties_changed(_collect_characteristics)

        self.characteristics_promise = dbus_callback_promise(self.device_interface.get_services_resolved).then(
            _get_now_or_later).catch(self.traceback_printer)
        return dbus_callback_promise(self.device_interface.call_connect)

    def disconnect(self):
        return dbus_callback_promise(self.device_interface.call_disconnect)

    def char_read(self, uuid):
        def _read_characteristic(characteristics):
            if uuid.casefold() in characteristics:
                characteristic = characteristics[uuid.casefold()]
                characteristic_interface = characteristic.get_interface(CHARACTERISTIC_IFACE)
                return dbus_callback_promise(characteristic_interface.call_read_value, {})

        return self.characteristics_promise.then(_read_characteristic)

    def char_write(self, uuid, value):
        def _write_characteristic(characteristics):
            if uuid.casefold() in characteristics:
                characteristic = characteristics[uuid.casefold()]
                characteristic_interface = characteristic.get_interface(CHARACTERISTIC_IFACE)
                return dbus_callback_promise(characteristic_interface.call_write_value, value, {})

        return self.characteristics_promise.then(_write_characteristic).catch(self.traceback_printer)

    def on_value_change(self, uuid, handler):
        uuid = uuid.casefold()
        notify_handler = CharacteristicNotifyHandler(handler)


        def _add_notification(characteristics):
            if uuid in characteristics:
                characteristic = characteristics[uuid]
                characteristic_properties_interface = characteristic.get_interface(PROPERTIES_IFACE)
                characteristic_interface = characteristic.get_interface(CHARACTERISTIC_IFACE)
            else:
                return Promise.reject(KeyError(f"UUID {uuid} not found"))

            def _remove_handler_on_start_notify_fail(error):
                characteristic_properties_interface.off_properties_changed(notify_handler)
                del self.handlers[uuid]

            def _check_flags(flags):
                if "notify" in flags or "indicate" in flags:
                    characteristic_properties_interface.on_properties_changed(notify_handler)
                    self.handlers[uuid].append(notify_handler)
                    return dbus_callback_promise(characteristic_interface.call_start_notify)
                else:
                    return Promise.reject(NotImplementedError(f"Notifications not implemented on {uuid}"))
            return dbus_callback_promise(characteristic_interface.get_flags).then(_check_flags).catch(self.traceback_printer)

        return self.characteristics_promise.then(_add_notification).catch(self.traceback_printer)

    def remove_notify(self, uuid):
        uuid = uuid.casefold()

        def _remove_notify(characteristics):
            if uuid in self.handlers and uuid in characteristics:
                characteristic = characteristics[uuid]

                characteristic_properties_interface = characteristic.get_interface(PROPERTIES_IFACE)
                characteristic_interface = characteristic.get_interface(CHARACTERISTIC_IFACE)
                for handler in self.handlers[uuid]:
                    characteristic_properties_interface.off_properties_changed(handler)

                del self.handlers[uuid]

                return dbus_callback_promise(characteristic_interface.call_stop_notify).catch(lambda _: Promise.resolve(None))


            return Promise.resolve(None)

        return self.characteristics_promise.then(_remove_notify).catch(self.traceback_printer)

    def _get_dbus_proxy_object(self, bus_name, path):
        return dbus_callback_promise(self.system_bus.introspect, bus_name, path) \
            .then(lambda introspection: self.system_bus.get_proxy_object(bus_name, path, introspection))


class WaterBottle:
    """
    right now contains logic for Hidrate Spark 3
    probably need to do lots of abstraction/generalizing
    to work with other water bottles, which I don't have or know about existing.
    """
    BOTTLE_SIZE = 592
    SIPS_CHARACTERISTIC_UUID = '016e11b1-6c8a-4074-9e5a-076053f93784'

    def __init__(self, name: str, device: BtleDevice, sip_stream: deque) -> None:
        """
        connect to device, find correct characteristic, read value, parse it,
        setup notifications then read sips
        """
        self.sip_stream = sip_stream

        self.traceback_printer = traceback_printer(self.__class__.__name__)
        self.device = device
        self.name = name
        self.device.connect().then(lambda _: self.device.on_value_change(self.SIPS_CHARACTERISTIC_UUID, self.sips_notification_handler))
        

        self.device.char_read(self.SIPS_CHARACTERISTIC_UUID) \
            .then(lambda value: value[0]) \
            .then(self.sips_notification_handler, self.traceback_printer)

    def sips_notification_handler(self, value):
        SipSize, total, secondsAgo, count_of_sips_on_device = self.parseSip(value)
        if SipSize > 0:
            self.sip_stream.appendleft((SipSize, datetime.now() - timedelta(milliseconds=secondsAgo), self.name))

        if count_of_sips_on_device > 0:
            self.device.char_write(self.SIPS_CHARACTERISTIC_UUID, bytes.fromhex("57"))

    def parseSip(self, data):
        """
        parses sips from data sent by water bottle.
        # diff-de5804e048e763f99ae84940f91d80e11b58f1b69da346d32a17abd6940e7db4R85
        code taken from https://github.com/choonkiatlee/wban-python/commit/3c644a32702f2a37e7a9c10f49bc5ebfcbf0a688
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
        self.device.remove_notify(self.SIPS_CHARACTERISTIC_UUID).then(lambda _: self.device.disconnect())
