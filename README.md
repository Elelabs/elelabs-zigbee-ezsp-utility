![Elelabs logo](/img/logo.jpg?raw=true)

---

# What is Elelabs Firmware Update Utility?


The Elelabs Firmware Update Utility is a basic Python 3 script to flash the the firmware inside a range of Elelabs Zigbee and Thread products to a newer version.

Currently sold supported products based on Silicon Labs microcontrollers:

- Elelabs Zigbee Raspberry Pi Shield ELR023 (EFR32MG13P Silicon Labs MCU inside)
  - https://elelabs.com/products/elelabs-zigbee-shield.html
- Elelabs Zigbee USB Adapter ELU013 (EFR32MG13P Silicon Labs MCU inside)
  - https://elelabs.com/products/elelabs-usb-adapter.html

Previously sold supported products based on Silicon Labs microcontrollers:
  
- Elelabs Zigbee Raspberry Pi Shield ELR022 (EFR32MG1B Silicon Labs MCU inside)
- Elelabs Zigbee USB Adapter ELU012 (EFR32MG1B Silicon Labs MCU inside)
- Elelabs Zigbee Raspberry Pi Shield EZBPIS (EM357 Silicon Labs MCU inside) TODO
- Elelabs Zigbee USB Adapter EZBUSBA (EM357 Silicon Labs MCU inside) TODO

Disclaimer: This utility should also work with other generic EZSP (EmberZNet Serial Protocol) or Spinel (Openthread Serial Protocol) based adapters and modules from other vendors, however firmwares for products not from Elelabs are not provided here and there is no guarantees that that it will work with non-Elelabs products. Be wanted that you may void your warranty and even brick your adapter if the firmware update is not supported by your mnaufacturer.

# Getting Started

- Download or clone the repository
- Get your Python3 ready
- Install the required packages using the `pip` utility
```
pip3 install -r requirements.txt
```
- Connect your Elelabs Zigbee/Thread Product to your PC or Raspberry Pi
- Find out the Serial port number of the Elelabs Zigbee/Thread Product

  * For Raspberry Pi Shield it is probably `/dev/ttyAMA0`
  * For USB Adapter on a Linux PC or Raspberry Pi it is probably `/dev/ttyUSB0` (the number 0 may be different)
  * For USB Adapter on a Windows PC it is probably `COM1` (the number 1 may be different)

- Launch the `probe` command to check if everything is working as expected

```
python3 Elelabs_EzspFwUtility.py probe -p /dev/ttyUSB0
```

![Elelabs Zigbee/Thread utility probe](/img/probe_zigbee.png?raw=true)

# How to
## ele_update – Switch Elelabs Zigbee/Thread Products between Zigbee and Thread

> only for Elelabs products

The `ele_update` is the easiest way of updating Elelabs Zigbee/Thread Products to a newer version or to switch between Zigbee and Thread version. The firmware update files are stored in the same repository and are automatically selected by the utility itself.

Switch/update to latest Zigbee

```
python3 Elelabs_EzspFwUtility.py ele_update -p /dev/ttyS6 -v zigbee
```

![Elelabs Zigbee/Thread utility ele_update zigbee](/img/ele_update_zigbee.png?raw=true)

Switch/update to latest Thread

```
python3 Elelabs_EzspFwUtility.py ele_update -p /dev/ttyS6 -v thread
```

![Elelabs Zigbee/Thread utility ele_update v6](/img/ele_update_thread.png?raw=true)

## probe – Check the version of the connected generic Zigbee/Thread product

> for any EZSP/Spinel product

The `probe` is used to detect the version of the connected Zigbee/Thread product or to detect if the product is in bootloader mode.

```
python3 Elelabs_EzspFwUtility.py probe -p /dev/ttyS6
```

Product in Zigbee EZSP mode

![Elelabs Zigbee/Thread utility probe](/img/probe_zigbee.png?raw=true)

Product in Thread Spinel mode

![Elelabs Zigbee/Thread utility probe](/img/probe_thread.png?raw=true)

Product in bootloader mode

![Elelabs Zigbee EZSP utility probe](/img/probe_btl.png?raw=true)

## restart – Restart the connected generic Zigbee/Thread product in Normal EZSP/Spinel mode or in Bootloader mode

> for any EZSP/Spinel product

The `restart` is used to probe the connected Zigbee/Thread product and restart it in normal or in bootloader mode. The normal mode is regular EZSP/Spinel operation. The bootloader mode is used only for the firmware update.

Switch from Normal mode to Bootloader mode

```
python3 Elelabs_EzspFwUtility.py restart -m btl -p /dev/ttyS6
```

![Elelabs Zigbee EZSP utility restart bootloader](/img/restart_btl.png?raw=true)

Switch from Bootloader mode to Normal mode

```
python3 Elelabs_EzspFwUtility.py restart -m nrml -p /dev/ttyS6
```

![Elelabs Zigbee EZSP utility restart normal](/img/restart_nrml.png?raw=true)

## flash – Perform Firmware Update on the generic EZSP product

> for any EZSP product

The `flash` is used to restart the connected EZSP product in bootloader mode and perform Firmware Update using XMODEM protocol. You need to provide an actual file for this utility. !!BE CAREFULL!! as this might damage or 'brick' your product.

```
python3 Elelabs_EzspFwUtility.py flash -f YOUR_NEW_EZSP_FIRMWARE_FILE.gbl -p /dev/ttyS6
```

# Recover

If for some reason the `update` or `flash` utility failed and your product is no longer responding.

1. `probe` the EZSP adapter as described. Most probably it is now in the Bootloader mode
2. try to `restart` the EZSP adapter in `nrml` mode. If success -> your product is working now
3. try to `flash` the EZSP adapter with the firmware file. If the product is in `btl` mode it will probably work
4. contact Elelabs: `info at elelabs.com`

# Integration

For integration with OpenHAB please see our [our OpenHAB user guide](https://elelabs.com/wp-content/uploads/2019/02/EZBUSBA_UG_3_OpenHab.pdf).

For integration with Home Assistant see [our Home Assistant user guide](https://elelabs.com/wp-content/uploads/2020/07/ELU013_UG_11_HomeAssistant_Hassio_0.112.4.pdf). *Please note if you are using the EZSP v8 firmware* you will also have to add the following to your `configuration.yaml` for the Home Assistant ZHA integration to load successfully. 

```
zha:
  zigpy_config:
    ezsp_config:
      CONFIG_APS_UNICAST_MESSAGE_COUNT: 12
      CONFIG_SOURCE_ROUTE_TABLE_SIZE: 16
      CONFIG_ADDRESS_TABLE_SIZE: 8
```
