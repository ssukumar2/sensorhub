#!/bin/bash
set -e
modprobe vcan
ip link add dev vcan0 type vcan 2>/dev/null || true
ip link set up vcan0
echo "vcan0 is up"
