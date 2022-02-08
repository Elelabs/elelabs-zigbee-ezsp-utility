# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [0.0.4] - 2022-02-08

- 1.2.3 OpenThread RCP Firmware for ELU013/ELR023 fix 

## [0.0.3] - 2021-12-11

- SPINEL OpenThread byte decoding bugfix
- 6.10.3 Zigbee Firmware for ELU0143 (just keep up with the latest EmberZnet SDK 6.10.3.0)
- 1.2.3 OpenThread RCP Firmware for ELU0143 (purely based on OpenThread RCP with minimal customisation OpenThread SDK 1.2.3.0)

## [0.0.2] - 2021-11-16

### Added

- Added support for Thread Spinel protocol to communicate with OpenThread compatible Serial Adapters
- 6.10.3 Zigbee Firmware for ELU013/ELR023 (just keep up with the latest EmberZnet SDK 6.10.3.0)
- 1.2.3 OpenThread RCP Firmware for ELU013/ELR023 (purely based on OpenThread RCP with minimal customisation OpenThread SDK 1.2.3.0)

### Changed

- `ele_update` parameters changed. Now the function only updates to latest version of available Zigbee or Thread firmware
- `probe` and `restart` functions can now detect Thread adapters as well

## [0.0.1] - 2020-08-02

### Added

- Initial public release of the EZSP Zigbee firmware update utility
- 6.03 Firmware for ELU013/ELR023 (EZSP v6)
- 6.70 Firmware for ELU013/ELR023 (EZSP v8)
