#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace sensorproto {

struct SensorReading
{
    int sensor_id;
    double value;
    std::string unit;
    std::string timestamp;
    std::string nonce;
};

/// Serialize a reading to JSON bytes.
std::vector<uint8_t> serialize(const SensorReading& reading);

/// Deserialize JSON bytes to a reading.
SensorReading deserialize(const std::vector<uint8_t>& data);

/// Unit string to byte code for compact encoding.
uint8_t unit_to_code(const std::string& unit);

/// Byte code back to unit string.
std::string code_to_unit(uint8_t code);

/// Encode a reading into a CAN frame (8 bytes).
/// Layout: sensor_id(2) + value_fixed_point(4) + unit_code(1) + flags(1)
std::vector<uint8_t> encode_can_frame(const SensorReading& reading);

/// Decode a CAN frame back to a reading.
SensorReading decode_can_frame(const std::vector<uint8_t>& frame);

} // namespace sensorproto