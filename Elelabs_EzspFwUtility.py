#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright 2020 Elelabs International Limited

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import time
import serial
import logging
import binascii
import argparse
from xmodem import XMODEM
from struct import pack

def is_valid_file(parser, arg):
    if not os.path.isfile(arg):
        parser.error("The file %s does not exist!" % arg)
    else:
        return arg

parser = argparse.ArgumentParser(description='Elelabs EZSP Serial FW Update utility')
subparsers = parser.add_subparsers(help='probe, restart, flash, ele_update')

parser_probe = subparsers.add_parser('probe', help='Check if Elelabs device responds and prints firmware version')
parser_probe.add_argument('-p','--port', type=str, required=True, help='Serial port for NCP')
parser_probe.add_argument('-b','--baudrate', type=str, required=False, default=115200, help='Serial baud rate for NCP (115200/57600)')
parser_probe.add_argument('-d','--dlevel', choices=['RAW', 'PACKET', 'DEBUG', 'INFO'], required=False, default='INFO', help='Debug verbosity level')
parser_probe.set_defaults(which='probe')

parser_restart = subparsers.add_parser('restart', help='Restart attached Elelabs Adapter into BOOTLOADER or NORMAL MODE')
parser_restart.add_argument('-m','--mode', choices=['btl', 'nrml'], required=True, help='Required operation mode')
parser_restart.add_argument('-p','--port', type=str, required=True, help='Serial port for NCP')
parser_restart.add_argument('-b','--baudrate', type=str, required=False, default=115200, help='Serial baud rate for NCP (115200/57600)')
parser_restart.add_argument('-d','--dlevel', choices=['RAW', 'PACKET', 'DEBUG', 'INFO'], required=False, default='INFO', help='Debug verbosity level')
parser_restart.set_defaults(which='restart')

parser_flash = subparsers.add_parser('flash', help='Performs update procedure on any generic EZSP product with a new application packaged in an GBL file.')
parser_flash.add_argument('-f', '--file', type=lambda x: is_valid_file(parser, x), required=True, help='GBL file to upload to the Elelabs product')
parser_flash.add_argument('-p','--port', type=str, required=True, help='Serial port for the EZSP Product')
parser_flash.add_argument('-b','--baudrate', type=str, required=False, default=115200, help='Serial baud rate for NCP (115200/57600)')
parser_flash.add_argument('-d','--dlevel', choices=['RAW', 'PACKET', 'DEBUG', 'INFO'], required=False, default='INFO', help='Debug verbosity level')
parser_flash.set_defaults(which='flash')

parser_ele_update = subparsers.add_parser('ele_update', help='Updates the Elelabs product to a latest available version')
parser_ele_update.add_argument('-v','--version', choices=['zigbee', 'thread'], required=True, help='Required protocol version')
parser_ele_update.add_argument('-p','--port', type=str, required=True, help='Serial port for the Elelabs Product')
parser_ele_update.add_argument('-b','--baudrate', type=str, required=False, default=115200, help='Serial baud rate for NCP (115200/57600)')
parser_ele_update.add_argument('-d','--dlevel', choices=['RAW', 'PACKET', 'DEBUG', 'INFO'], required=False, default='INFO', help='Debug verbosity level')
parser_ele_update.set_defaults(which='ele_update')

class AdapterModeProbeStatus:
    ZIGBEE = 0
    THREAD = 1
    BOOTLOADER = 2
    ERROR = 3

class SerialInterface:
    def __init__(self, port, baudrate):
        self.port = port
        self.baudrate = baudrate

    def open(self):
        try:
            self.serial = serial.Serial(port=self.port,
                baudrate=self.baudrate,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=True,
                timeout=3)
        except Exception as e:
            raise Exception("PORT ERROR: %s" % str(e))

    def close(self):
        self.serial.close()

class AshProtocolInterface:
    FLAG_BYTE = b'\x7E'
    RANDOMIZE_START =  0x42
    RANDOMIZE_SEQ = 0xB8
    RSTACK_FRAME_CMD = b'\x1A\xC0\x38\xBC\x7E'
    RSTACK_FRAME_ACK = b'\x1A\xC1\x02\x0B\x0A\x52\x7E'

    def __init__(self, serial, config, logger):
        self.logger = logger
        self.config = config
        self.serial = serial

        self.ackNum = 0
        self.frmNum = 0

    def dataRandomize(self, frame):
        rand = self.RANDOMIZE_START
        out = bytearray()
        for x in frame:
            out += bytearray([x ^ rand])
            if rand % 2:
                rand = (rand >> 1) ^ self.RANDOMIZE_SEQ
            else:
                rand = rand >> 1
        return out

    def ashFrameBuilder(self, ezsp_frame):
        ash_frame = bytearray()
        # Control byte
        ash_frame += bytearray([(((self.ackNum << 0) & 0xFF) | (((self.frmNum % 8) << 4 ) & 0xFF)) & 0xFF])
        self.ackNum = (self.ackNum + 1) % 8
        self.frmNum = (self.frmNum + 1) % 8
        ash_frame += self.dataRandomize(ezsp_frame)
        crc = binascii.crc_hqx(ash_frame, 0xFFFF)
        ash_frame += bytearray([crc >> 8, crc & 0xFF])
        ash_frame = self.replaceReservedBytes(ash_frame)
        ash_frame += self.FLAG_BYTE
        if self.config.dlevel == 'RAW':
            self.logger.debug('[ ASH  REQUEST ] ' + ' '.join(format(x, '02x') for x in ash_frame))
        return ash_frame

    def revertEscapedBytes(self, msg):
        msg = msg.replace(b'\x7d\x5d', b'\x7d')
        msg = msg.replace(b'\x7d\x5e', b'\x7e')
        msg = msg.replace(b'\x7d\x31', b'\x11')
        msg = msg.replace(b'\x7d\x33', b'\x13')
        msg = msg.replace(b'\x7d\x38', b'\x18')
        msg = msg.replace(b'\x7d\x3a', b'\x1a')
        return msg

    def replaceReservedBytes(self, msg):
        msg = msg.replace(b'\x7d', b'\x7d\x5d')
        msg = msg.replace(b'\x7e', b'\x7d\x5e')
        msg = msg.replace(b'\x11', b'\x7d\x31')
        msg = msg.replace(b'\x13', b'\x7d\x33')
        msg = msg.replace(b'\x18', b'\x7d\x38')
        msg = msg.replace(b'\x1a', b'\x7d\x3a')
        return msg

    def getResponse(self, applyRandomize = False):
        timeout = time.time() + 3
        msg = bytearray()

        receivedbyte = None

        while (time.time() < timeout) and (receivedbyte != self.FLAG_BYTE):
            receivedbyte = self.serial.read()
            msg += receivedbyte

        if len(msg) == 0:
            return -1, None, None

        msg = self.revertEscapedBytes(msg)

        if self.config.dlevel == 'RAW':
            self.logger.debug('[ ASH RESPONSE ] ' + ' '.join(format(x, '02x') for x in msg))

        if applyRandomize:
            msg_parsed = self.dataRandomize(bytearray(msg[1:-3]))
            if self.config.dlevel == 'RAW' or self.config.dlevel == 'PACKET':
                self.logger.debug('[ EZSP RESPONSE ] ' + ' '.join(format(x, '02x') for x in msg_parsed))
            return 0, msg, msg_parsed
        else:
            return 0, msg, None

    def sendResetFrame(self):
        self.serial.flushInput()
        self.logger.debug('RESET FRAME')
        if self.config.dlevel == 'RAW':
            self.logger.debug('[ ASH  REQUEST ] ' + ' '.join(format(x, '02x') for x in self.RSTACK_FRAME_CMD))
        self.serial.write(self.RSTACK_FRAME_CMD)
        status, ash_response, ezsp_response = self.getResponse()

        if status:
            return status

        if not (self.RSTACK_FRAME_ACK in ash_response):
            return -1

        return 0

    def sendAck(self, ackNum):
        ack = bytearray([ackNum & 0x07 | 0x80])
        crc = binascii.crc_hqx(ack, 0xFFFF)
        ack += bytearray([crc >> 8, crc & 0xFF])
        ack = self.replaceReservedBytes(ack)
        ack += self.FLAG_BYTE

        if self.config.dlevel == 'RAW':
            self.logger.debug('[ ASH ACK ] ' + ' '.join(format(x, '02x') for x in ack))
        self.serial.write(ack)

    def sendAshCommand(self, ezspFrame):
        ash_frame = self.ashFrameBuilder(ezspFrame)
        self.serial.flushInput()
        self.serial.write(ash_frame)
        status, ash_response, ezsp_response = self.getResponse(True)
        if status:
            return status, None

        self.sendAck(ash_response[0])
        return 0, ezsp_response

class EzspProtocolInterface:
    def __init__(self, serial, config, logger):
        self.logger = logger
        self.config = config

        self.INITIAL_EZSP_VERSION = 4

        self.VERSION = b'\x00'
        self.GET_VALUE = b'\xAA'
        self.GET_MFG_TOKEN = b'\x0B'
        self.LAUNCH_STANDALONE_BOOTLOADER = b'\x8F'

        self.EZSP_VALUE_VERSION_INFO = 0x11
        self.EZSP_MFG_STRING = 0x01
        self.EZSP_MFG_BOARD_NAME = 0x02
        self.STANDALONE_BOOTLOADER_NORMAL_MODE = 1

        self.ezspVersion = self.INITIAL_EZSP_VERSION
        self.sequenceNum = 0
        self.ash = AshProtocolInterface(serial, config, logger)

    def ezspFrameBuilder(self, command):
        ezsp_frame = bytearray()

        # Sequence byte
        ezsp_frame += bytearray([self.sequenceNum])
        self.sequenceNum = (self.sequenceNum + 1) % 255
        ezsp_frame += b'\x00'
        if self.ezspVersion >=5:
            # Legacy frame ID - always 0xFF
            ezsp_frame += b'\xFF'
            # Extended frame control
            ezsp_frame += b'\x00'

        ezsp_frame = ezsp_frame + command

        if self.ezspVersion >= 8:
            ezsp_frame[2] = 0x01
            ezsp_frame[3] = command[0] & 0xFF # LSB
            ezsp_frame[4] = command[0] >> 8  # MSB

        if self.config.dlevel == 'RAW' or self.config.dlevel == 'PACKET':
            self.logger.debug('[ EZSP  REQUEST ] ' + ' '.join(format(x, '02x') for x in ezsp_frame))
        return ezsp_frame

    def sendEzspCommand(self, commandData, commandName = ''):
        self.logger.debug(commandName)
        status, response = self.ash.sendAshCommand(self.ezspFrameBuilder(commandData))
        if status:
            raise Exception("sendAshCommand status error: %d" % status)

        return response

    def sendVersion(self, desiredProtocolVersion):
        resp = self.sendEzspCommand(self.VERSION + bytearray([desiredProtocolVersion]), 'sendVersion: V%d' % desiredProtocolVersion)
        return resp[3] # protocolVersion

    def getValue(self, valueId, valueIdName):
        resp = self.sendEzspCommand(self.GET_VALUE + bytearray([valueId]), 'getValue: %s' % valueIdName)
        status = resp[5]
        valueLength = resp[6]
        valueArray = resp[7:]
        return status, valueLength, valueArray

    def getMfgToken(self, tokenId, tokenIdName):
        resp = self.sendEzspCommand(self.GET_MFG_TOKEN + bytearray([tokenId]), 'getMfgToken: %s' % tokenIdName)
        tokenDataLength = resp[5]
        tokenData = resp[6:]
        return tokenDataLength, tokenData

    def launchStandaloneBootloader(self, mode, modeName):
        resp = self.sendEzspCommand(self.LAUNCH_STANDALONE_BOOTLOADER + bytearray([mode]), 'launchStandaloneBootloader: %s' % modeName)
        status = resp[5]
        return status

    def initEzspProtocol(self):
        ash_status = self.ash.sendResetFrame()
        if ash_status:
            return ash_status

        self.ezspVersion = self.sendVersion(self.INITIAL_EZSP_VERSION)
        self.logger.debug("EZSP v%d detected" % self.ezspVersion)
        if (self.ezspVersion != self.INITIAL_EZSP_VERSION):
            self.sendVersion(self.ezspVersion)

        return 0

class HdlcLiteProtocolInterface:
    HDLC_FLAG = 0x7e
    HDLC_ESCAPE = 0x7d

    HDLC_FCS_INIT = 0xFFFF
    HDLC_FCS_POLY = 0x8408
    HDLC_FCS_GOOD = 0xF0B8

    def __init__(self, serial, config, logger):
        self.logger = logger
        self.config = config
        self.serial = serial
        self.fcstab = self.mkfcstab()

    def mkfcstab(self):
        """ Make a static lookup table for byte value to FCS16 result. """
        polynomial = self.HDLC_FCS_POLY

        def valiter():
            """ Helper to yield FCS16 table entries for each byte value. """
            for byte in range(256):
                fcs = byte
                i = 8
                while i:
                    fcs = (fcs >> 1) ^ polynomial if fcs & 1 else fcs >> 1
                    i -= 1

                yield fcs & 0xFFFF

        return tuple(valiter())

    def fcs16(self, byte, fcs):
        fcs = (fcs >> 8) ^ self.fcstab[(fcs ^ byte) & 0xff]
        return fcs

    def getResponse(self):
        fcs = self.HDLC_FCS_INIT
        timeout = time.time() + 3
        packet = bytearray()

        while (time.time() < timeout):
            byte = int.from_bytes(self.serial.read(1), "little")
            if byte == self.HDLC_FLAG:
                if len(packet) == 0:
                    # First sync byte
                    continue
                else:
                    # end of packet, go parse
                    break
            if byte == self.HDLC_ESCAPE:
                byte = int.from_bytes(self.serial.read(1), "little")
                byte ^= 0x20
            packet.append(byte)
            fcs = self.fcs16(byte, fcs)

        if len(packet) == 0:
            return -1, None

        if self.config.dlevel == 'RAW':
            self.logger.debug('[ HDLC RESPONSE ]: 7e ' + ' '.join(format(x, '02x') for x in packet) + ' 7e')
        
        if fcs != self.HDLC_FCS_GOOD:
            return -1, None
        else:
            packet = packet[:-2]  # remove FCS16 from end
            packet = pack("%dB" % len(packet), *packet)

        return 0, packet

    def encode_byte(self, byte, packet=[]):
        """ HDLC encode and append a single byte to the given packet. """
        if (byte == self.HDLC_ESCAPE) or (byte == self.HDLC_FLAG):
            packet.append(self.HDLC_ESCAPE)
            packet.append(byte ^ 0x20)
        else:
            packet.append(byte)
        return packet

    def encode(self, payload=""):
        """ Return the HDLC encoding of the given packet. """
        fcs = self.HDLC_FCS_INIT
        packet = []
        packet.append(self.HDLC_FLAG)
        for byte in payload:
            fcs = self.fcs16(byte, fcs)
            packet = self.encode_byte(byte, packet)

        fcs ^= 0xffff
        byte = fcs & 0xFF
        packet = self.encode_byte(byte, packet)
        byte = fcs >> 8
        packet = self.encode_byte(byte, packet)
        packet.append(self.HDLC_FLAG)
        packet = pack("%dB" % len(packet), *packet)

        if self.config.dlevel == 'RAW':
            self.logger.debug("[ HDLC  REQUEST ]: " + ' '.join(format(x, '02x') for x in packet))
        return packet

    def sendHdlcPacket(self, data):
        pkt = self.encode(data)
        self.serial.write(pkt)

        return self.getResponse()

class SpinelProtocolInterface:
    CMD_PROP_VALUE_GET = 2
    CMD_PROP_VALUE_SET = 3

    HEADER_ASYNC = 0x80
    HEADER_DEFAULT = 0x81

    PROP_PROTOCOL_VERSION = 1  # < major, minor [i,i]
    PROP_NCP_VERSION = 2  # < version string [U]

    PROP_MFG_CUSTOM_VERSION = 0x3C00
    PROP_MFG_STRING = 0x3C01
    PROP_MFG_BOARD_NAME = 0x3C02

    CMD_RESET = 1
    CMD_MFG_LAUNCH_BOOTLOADER = 15360

    def __init__(self, serial, config, logger):
        self.logger = logger
        self.config = config

        self.spinelVersion = ""
        self.hdlc = HdlcLiteProtocolInterface(serial, config, logger)

    def encode_i(self, data):
        result = bytes()
        while data:
            value = data & 0x7F
            data >>= 7
            if data:
                value |= 0x80
            result = result + pack("<B", value)
        return result

    def encode_packet(self,
                      command_id,
                      payload=bytes()):
        header = pack(">B", self.HEADER_DEFAULT)
        cmd = self.encode_i(command_id)
        pkt = header + cmd + payload
        return pkt

    def sendSpinelCommand(self, command_id, commandName = '', payload=bytes()):
        self.logger.debug(commandName)

        pkt = self.encode_packet(command_id, payload)

        if self.config.dlevel == 'RAW' or self.config.dlevel == 'PACKET':
            self.logger.debug("[ SPINEL   REQUEST ]: " + ' '.join(format(x, '02x') for x in pkt))

        status, response = self.hdlc.sendHdlcPacket(pkt)

        if status:
            raise Exception("sendHdlcPacket status error: %d" % status)

        if self.config.dlevel == 'RAW' or self.config.dlevel == 'PACKET':
            self.logger.debug("[ SPINEL  RESPONSE ]: " + ' '.join(format(x, '02x') for x in response))

        return response

    def propValueGet(self, prop_id):
        resp = self.sendSpinelCommand(self.CMD_PROP_VALUE_GET, 'CMD_PROP_VALUE_GET %d' % (prop_id), self.encode_i(prop_id))

        if (prop_id > 0xFFFF):
            raise Exception("prop_id is more than 0xFFFF. Not sure what to do")
        elif (prop_id > 0xFF):
            return resp[4:]
        else:
            return resp[3:]

    def eleLaunchBtl(self):
        header = pack(">B", self.HEADER_ASYNC)
        cmd = self.encode_i(self.CMD_MFG_LAUNCH_BOOTLOADER)
        pkt = header + cmd

        if self.config.dlevel == 'RAW' or self.config.dlevel == 'PACKET':
            self.logger.debug("[ SPINEL   REQUEST ]: " + ' '.join(format(x, '02x') for x in pkt))

        self.hdlc.sendHdlcPacket(pkt)

    def initSpinelProtocol(self):
        self.spinelVersion = ""

        header = pack(">B", self.HEADER_ASYNC)
        cmd = self.encode_i(self.CMD_RESET)
        pkt = header + cmd

        if self.config.dlevel == 'RAW' or self.config.dlevel == 'PACKET':
            self.logger.debug("[ SPINEL   REQUEST ]: " + ' '.join(format(x, '02x') for x in pkt))

        status, response = self.hdlc.sendHdlcPacket(pkt)

        if status:
            return status
        
        if response == pkt:
            self.logger.debug("Received same SPINEL packet. That's bootloader echo")
            return -1


        if self.config.dlevel == 'RAW' or self.config.dlevel == 'PACKET':
            self.logger.debug("[ SPINEL  RESPONSE ]: " + ' '.join(format(x, '02x') for x in response))

        # request version of the SPINEL protocol
        counter = 0
        while self.spinelVersion == "":
            response = self.sendSpinelCommand(self.CMD_PROP_VALUE_GET, 'CMD_PROP_VALUE_GET %d' % (self.PROP_PROTOCOL_VERSION), self.encode_i(self.PROP_PROTOCOL_VERSION))
            if response[2] != self.PROP_PROTOCOL_VERSION:
                # missmatch, request again
                counter = counter + 1
                if counter >= 5:
                    return -1
                else:
                    continue
            self.spinelVersion = "%d.%d"% (response[3],response[4])
            self.logger.debug("SPINEL v%s detected" % (self.spinelVersion))
            break

        return 0


class ElelabsUtilities:
    def __init__(self, config, logger):
        self.logger = logger
        self.config = config

    def probe(self):
        serialInterface = SerialInterface(self.config.port, self.config.baudrate)
        serialInterface.open()

        ezsp = EzspProtocolInterface(serialInterface.serial, self.config, self.logger)
        ezsp_status = ezsp.initEzspProtocol()
        if ezsp_status == 0:
            status, value_length, value_array = ezsp.getValue(ezsp.EZSP_VALUE_VERSION_INFO, "EZSP_VALUE_VERSION_INFO")
            if (status == 0):
                firmware_version = str(value_array[2]) + '.' + str(value_array[3]) + '.' + str(value_array[4]) + '-' + str(value_array[0])
            else:
                self.logger.info('EZSP status returned %d' % status)

            token_data_length, token_data = ezsp.getMfgToken(ezsp.EZSP_MFG_STRING, "EZSP_MFG_STRING")
            if token_data.decode("ascii", "ignore") == "Elelabs":
                token_data_length, token_data = ezsp.getMfgToken(ezsp.EZSP_MFG_BOARD_NAME, "EZSP_MFG_BOARD_NAME")
                adapter_name = token_data.decode("ascii", "ignore")

                self.logger.info("Elelabs Zigbee adapter detected:")
                self.logger.info("Adapter: %s" % adapter_name)
            else:
                adapter_name = None
                self.logger.info("Generic Zigbee EZSP adapter detected:")

            self.logger.info("Firmware: %s" % firmware_version)
            self.logger.info("EZSP v%d" % ezsp.ezspVersion)

            serialInterface.close()
            return AdapterModeProbeStatus.ZIGBEE, adapter_name
        else:
            spinel = SpinelProtocolInterface(serialInterface.serial, self.config, self.logger)
            spinel_status = spinel.initSpinelProtocol()
            if spinel_status == 0:
                property_data = spinel.propValueGet(spinel.PROP_NCP_VERSION)
                firmware_version = property_data.decode("ascii", "ignore")

                property_data = spinel.propValueGet(spinel.PROP_MFG_STRING)
                vendor_name = property_data.decode("ascii", "ignore").rstrip('\x00')
                if vendor_name == "Elelabs":
                    property_data = spinel.propValueGet(spinel.PROP_MFG_BOARD_NAME)
                    adapter_name = property_data.decode("ascii", "ignore").rstrip('\x00')
                    
                    self.logger.info("Elelabs Thread adapter detected:")
                    self.logger.info("Adapter: %s"%adapter_name)
                else:
                    adapter_name = None
                    self.logger.info("Generic Thread adapter detected:")

                self.logger.info("Firmware: %s"%firmware_version)
                self.logger.info("SPINEL v%s" % spinel.spinelVersion)

                serialInterface.close()
                return AdapterModeProbeStatus.THREAD, adapter_name
            else:
                if self.config.baudrate != 115200:
                    serialInterface.close()
                    time.sleep(1)
                    serialInterface = SerialInterface(self.config.port, 115200)
                    serialInterface.open()

                # check if allready in bootloader mode
                serialInterface.serial.write(b'\x0D')
                first_line = serialInterface.serial.readline() # read blank line
                if len(first_line) == 0:
                    # timeout
                    serialInterface.close()
                    self.logger.info("Couldn't communicate with the adapter in Zigbee (EZSP) mode, Thread (Spinel) mode or bootloader mode")
                    return AdapterModeProbeStatus.ERROR, None

                btl_info = serialInterface.serial.readline() # read Gecko BTL version or blank line

                self.logger.info("EZSP adapter in bootloader mode detected:")
                self.logger.info(btl_info.decode("ascii", "ignore")[:-2]) # show Bootloader version
                serialInterface.close()
                return AdapterModeProbeStatus.BOOTLOADER, None

    def restart(self, mode):
        adapter_status, adapter_name = self.probe()
        if adapter_status == AdapterModeProbeStatus.ZIGBEE or adapter_status == AdapterModeProbeStatus.THREAD:
            if mode == 'btl':
                serialInterface = SerialInterface(self.config.port, self.config.baudrate)
                serialInterface.open()

                self.logger.info("Launch in bootloader mode")
                if adapter_status == AdapterModeProbeStatus.ZIGBEE:
                    ezsp = EzspProtocolInterface(serialInterface.serial, self.config, self.logger)
                    ezsp_status = ezsp.initEzspProtocol()
                    status = ezsp.launchStandaloneBootloader(ezsp.STANDALONE_BOOTLOADER_NORMAL_MODE, "STANDALONE_BOOTLOADER_NORMAL_MODE")
                    if status:
                        serialInterface.close()
                        self.logger.critical("Error launching the adapter in bootloader mode")
                        return -1
                else:
                    if adapter_name == None:
                        self.logger.critical("No Elelabs Thread product detected.\r\nWe don't know how to force it into bootloader mode.\r\n Manually launch the product into bootloader mode")
                        return -1

                    spinel = SpinelProtocolInterface(serialInterface.serial, self.config, self.logger)
                    spinel_status = spinel.initSpinelProtocol()
                    if spinel_status:
                        serialInterface.close()
                        self.logger.critical("Error launching the adapter in bootloader mode")
                        return -1
                    spinel.eleLaunchBtl()

                serialInterface.close()
                # wait for reboot
                time.sleep(2)

                adapter_status, adapter_name = self.probe()
                if adapter_status == AdapterModeProbeStatus.BOOTLOADER:
                    return 0
                else:
                    return -1
            else:
                self.logger.info("Allready in normal mode. No need to restart")
                return 0
        elif adapter_status == AdapterModeProbeStatus.BOOTLOADER:
            if mode == 'btl':
                self.logger.info("Allready in bootloader mode. No need to restart")
                return 0
            else:
                serialInterface = SerialInterface(self.config.port, 115200)
                serialInterface.open()

                self.logger.info("Launch in normal application mode")

                # Send Reboot
                serialInterface.serial.write(b'2')
                serialInterface.close()

                # wait for reboot
                time.sleep(2)

                adapter_status, adapter_name = self.probe()
                if adapter_status == AdapterModeProbeStatus.ZIGBEE or adapter_status == AdapterModeProbeStatus.THREAD:
                    return 0
                else:
                    return -1

    def flash(self, filename):
        # STATIC FUNCTIONS
        def getc(size, timeout=1):
            read_data = self.serialInterface.serial.read(size)
            return read_data

        def putc(data, timeout=1):
            self.currentPacket += 1
            if (self.currentPacket % 20) == 0:
                print('.', end = '')
            if (self.currentPacket % 100) == 0:
                print('')
            self.serialInterface.serial.write(data)
            time.sleep(0.001)

        if not (".gbl" in filename) and not (".ebl" in filename):
            self.logger.critical('Aborted! Gecko bootloader accepts .gbl or .ebl images only.')
            return

        if self.restart("btl"):
            self.logger.critical("EZSP adapter not in the bootloader mode. Can't perform update procedure")
            return

        self.serialInterface = SerialInterface(self.config.port, 115200)
        self.serialInterface.open()
        # Enter '1' to initialize X-MODEM mode
        self.serialInterface.serial.write(b'\x0A')
        self.serialInterface.serial.write(b'1')
        time.sleep(1)
        self.serialInterface.serial.readline() # BL > 1
        self.serialInterface.serial.readline() # begin upload

        self.logger.info('Successfully restarted into X-MODEM mode! Starting upload of the new firmware... DO NOT INTERRUPT(!)')

        self.currentPacket = 0
        # Wait for char 'C'
        success = False
        start_time = time.time()
        while time.time()-start_time < 10:
            if self.serialInterface.serial.read() == b'C':
                success = True
                if time.time()-start_time > 5:
                    break
        if not success:
            self.logger.info('Failed to restart into bootloader mode. Please see users guide.')
            return
        
        # Start XMODEM transaction
        modem = XMODEM(getc, putc)
        stream = open(filename,'rb')
        sentcheck = modem.send(stream)

        print('')
        if sentcheck:
            self.logger.info('Firmware upload complete')
        else:
            self.logger.critical('Firmware upload failed. Please try a correct firmware image or restart in normal mode.')
            return
        self.logger.info('Rebooting NCP...')
        # Wait for restart
        time.sleep(4)
        # Send Reboot into App-Code command
        self.serialInterface.serial.write(b'2')
        self.serialInterface.close()
        time.sleep(2)
        self.probe()


    def ele_update(self, new_version):
        adapter_status, adapter_name = self.probe()
        if adapter_status == AdapterModeProbeStatus.ZIGBEE or adapter_status == AdapterModeProbeStatus.THREAD:
            if adapter_name == None:
                self.logger.critical("No Elelabs product detected.\r\nUse 'flash' utility for generic EZSP products.\r\nContact info@elelabs.com if you see this message for original Elelabs product")
                return

            if adapter_name == "ELR023" or adapter_name == "ELU013":
                if new_version == 'thread':
                    self.flash("data/EFR32MG13/ELE_MG13_ot_rcp_123_220206.gbl")
                elif new_version == 'zigbee':
                    self.flash("data/EFR32MG13/ELE_MG13_zb_ncp_115200_610_211112.gbl")
                else:
                    self.logger.critical("Unknown protocol version " + new_version)
            elif adapter_name == "ELR022" or adapter_name == "ELU012":
                self.logger.critical("TODO!. Contact Elelabs at info@elelabs.com")
            elif adapter_name == "EZBPIS" or adapter_name == "EZBUSBA":
                self.logger.critical("TODO!. Contact Elelabs at info@elelabs.com")
            elif adapter_name == "ELU0143":
                if new_version == 'thread':
                    self.flash("data/EFR32MG21/ELU0143_MG21_ot_rcp_123_220131.gbl")
                elif new_version == 'zigbee':
                    self.flash("data/EFR32MG21/ELU0143_MG21_zb_ncp_6103_220131.gbl")
                else:
                    self.logger.critical("Unknown protocol version " + new_version)
            elif adapter_name == "ELU0141" or adapter_name == "ELU0142":
                if new_version == 'thread':
                    self.flash("data/EFR32MG21/ELU0141_MG21_ot_rcp_123_211204.gbl")
                elif new_version == 'zigbee':
                    self.flash("data/EFR32MG21/ELU0141_MG21_zb_ncp_6103_211204.gbl")
                else:
                    self.logger.critical("Unknown protocol version " + new_version)
            else:
                self.logger.critical("Unknown Elelabs product %s detected.\r\nContact info@elelabs.com if you see this message for original Elelabs product" % adapter_name)
        elif adapter_status == AdapterModeProbeStatus.BOOTLOADER:
            self.logger.critical("The product not in the normal EZSP mode.\r\n'restart' into normal mode or use 'flash' utility instead")
        else:
            self.logger.critical("No upgradable device found")




args = parser.parse_args()

main_app_loger = logging.getLogger("Elelabs_EzspFwUtility")
if args.dlevel == 'INFO':
    main_app_loger.setLevel(logging.INFO)
else:
    main_app_loger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s %(name)s:   %(message)s", datefmt="%Y/%m/%d %H:%M:%S")
streamHandler = logging.StreamHandler()
streamHandler.setFormatter(formatter)
main_app_loger.addHandler(streamHandler)

elelabs = ElelabsUtilities(args, main_app_loger)

if args.which == 'restart':
    elelabs.restart(args.mode)

if args.which == 'probe':
    elelabs.probe()

if args.which == 'ele_update':
    elelabs.ele_update(args.version)

if args.which == 'flash':
    elelabs.flash(args.file)







