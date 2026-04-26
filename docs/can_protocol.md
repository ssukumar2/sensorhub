# CAN bus protocol for sensorhub

## Overview

The C++ sensor client can transmit readings over CAN bus using Linux SocketCAN. This is the third transport option alongside HTTP and MQTT. A Python CAN receiver on the backend side decodes the frames and writes them to the same SQLite database used by the other transports.

CAN (Controller Area Network) is a serial bus protocol originally designed for automotive use. All nodes share a single bus and messages are broadcast, meaning every node sees every frame. Priority is determined by the message ID: lower ID wins arbitration. There is no master/slave relationship.

## Frame layout

Each sensor reading is packed into a single standard CAN 2.0A frame with 8 data bytes:

    Byte 0-1: sensor_id (uint16, big-endian)
    Byte 2-5: value * 100 as int32 (big-endian, fixed-point encoding)
    Byte 6:   unit code
    Byte 7:   flags (reserved, currently 0x00)

The fixed-point encoding multiplies the float value by 100 and truncates to an integer. For example, a temperature of 22.5 degrees becomes 2250. The receiver divides by 100 to recover the original value. This avoids floating-point representation in the CAN payload.

## Unit codes

    0x01  celsius
    0x02  fahrenheit
    0x03  percent
    0x04  hpa (hectopascal)
    0x05  lux
    0x06  voltage
    0x07  ampere
    0x08  watt

## CAN ID assignment

Each sensor transmits on CAN ID 0x100 + sensor_id. For example, sensor 1 uses CAN ID 0x101, sensor 2 uses 0x102, and so on. This allows the receiver to identify the sensor from the CAN ID alone without parsing the payload, and ensures each sensor has a unique priority on the bus.

## Development setup with virtual CAN

Linux provides a virtual CAN interface (vcan) for development and testing without real hardware. Set it up with:

    sudo modprobe vcan
    sudo ip link add dev vcan0 type vcan
    sudo ip link set up vcan0

Or use the provided script:

    sudo ./scripts/setup_vcan.sh

Monitor traffic on the virtual bus:

    candump vcan0

Send a test frame manually:

    cansend vcan0 101#08CA00000001000

This sends sensor_id=1, value=22.50 (0x08CA = 2250), unit=celsius (0x01).

## Running

Start the backend and CAN receiver:

    uvicorn app.main:app --reload
    python3 -m app.can.receiver

Run the C++ client in CAN mode:

    cd client-cpp
    ./build/sensor_client --mode=can

Readings will appear in the CAN receiver output and be queryable through the REST API just like HTTP and MQTT readings.