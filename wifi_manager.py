from ble import (
    Advertisement,
    Characteristic,
    Service,
    Application,
    find_adapter,
    Descriptor,
    Agent,
)

import logging
import array
import subprocess
import re

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logHandler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)


class WifiAdvertisement(Advertisement):
    def __init__(self, bus, index):
        logger.info("Advertisement WIFI")
        Advertisement.__init__(self, bus, index, "peripheral")
        self.add_manufacturer_data(
            0xFFFF,
            [0x70, 0x74],
        )
        self.add_service_uuid(WifiS1Service.WIFI_SVC_UUID)

        self.add_local_name("Wifi")
        self.include_tx_power = True


class WifiS1Service(Service):
    """
    Service that manages pi wifi settings
    """

    WIFI_SVC_UUID = "b94dda26-b922-11ed-afa1-0242ac120002"

    def __init__(self, bus, index):
        Service.__init__(self, bus, index, self.WIFI_SVC_UUID, True)
        self.add_characteristic(WifiCredsCharacteristic(bus, 0, self))
        self.add_characteristic(MachineIdCharacteristic(bus, 1, self))


class WifiCredsCharacteristic(Characteristic):
    uuid = "8d90bb40-bd1b-11ed-afa1-0242ac120002"
    description = b"Get/set wifi credentials"

    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self,
            bus,
            index,
            self.uuid,
            ["encrypt-read", "encrypt-write"],
            service,
        )

        self.value = [0xFF]
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))

    def ReadValue(self, options):
        logger.debug("Wifi Creds Read: " + repr(self.value))
        res = None
        try:
            output = subprocess.check_output(["iwconfig", "wlan0"]).decode()
            lines = output.split("\n")
            for line in lines:
                matches = re.match(r'.*ESSID:"(.*)"', line, re.M | re.I)
                if matches:
                    wifi_name = matches.group(1)
            self.value = bytearray(wifi_name, encoding="utf8")
        except Exception as e:
            logger.error(f"Error getting status {e}")
            self.value = bytearray("NONE", encoding="utf8")

        return self.value

    def WriteValue(self, value, options):
        try:
            logger.debug("Wifi Creds Write: " + repr(value))
            creds = bytes(value).decode("utf-8")
            configs = creds.split("%&%")

            # TODO check for split
            # TODO encrypt

            # Read in the file
            with open("/etc/wpa_supplicant/wpa_supplicant.conf", "r") as file:
                filedata = file.read()

                if "network={" in filedata:
                    # Replace ssid
                    ssid = f'ssid="{configs[0]}"'
                    filedata = re.sub("ssid=(.*)", ssid, filedata)

                    # Replace psk
                    psk = f'psk="{configs[1]}"'
                    filedata = re.sub("psk=(.*)", psk, filedata)
                else:
                    logger.debug("the network...")

                    ssid = configs[0]
                    password = configs[1]

                    network = f'\n network={{\nssid="{ssid}"\npsk="{password}"\nkey_mgmt=WPA-PSK\n}}'

                    logger.debug("is...")
                    logger.debug(network)

                    filedata = filedata + network

                    logger.debug("THE NEW FILE DATA:")

                logger.debug(filedata)

                # filedata = filedata.replace('abcd', 'ram')
                # Write the file out again
                with open("/etc/wpa_supplicant/wpa_supplicant.conf", "w") as file:
                    file.write(filedata)

                logger.debug("File Written Successfully")

            # restart wifi with new credentials
            subprocess.call(["sudo", "wpa_cli", "-i", "wlan0", "reconfigure"])

        except Exception as e:
            logger.error(f"ERRRRRRROR: {e}")

        self.value = value


class MachineIdCharacteristic(Characteristic):
    uuid = "36d7c74e-bc6c-11ed-afa1-0242ac120002"
    description = b"Get machine id"

    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self,
            bus,
            index,
            self.uuid,
            ["encrypt-read"],
            service,
        )

        self.value = [0xFF]
        self.add_descriptor(CharacteristicUserDescriptionDescriptor(bus, 1, self))

    def ReadValue(self, options):
        filedata = None
        try:
            with open("/var/lib/dbus/machine-id", "r") as file:
                filedata = file.read()
                self.value = bytearray(filedata, encoding="utf8")
        except Exception as e:
            logger.error(f"Error getting status {e}")
            self.value = bytearray("NONE", encoding="utf8")

        return self.value


class CharacteristicUserDescriptionDescriptor(Descriptor):
    """
    Writable CUD descriptor.
    """

    CUD_UUID = "2901"

    def __init__(
        self,
        bus,
        index,
        characteristic,
    ):
        self.value = array.array("B", characteristic.description)
        self.value = self.value.tolist()
        Descriptor.__init__(self, bus, index, self.CUD_UUID, ["read"], characteristic)

    def ReadValue(self, options):
        return self.value

    def WriteValue(self, value, options):
        if not self.writable:
            raise NotPermittedException()
        self.value = value
