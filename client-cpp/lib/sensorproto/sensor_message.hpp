#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace sensorproto {

/// A single sensor reading ready for transmission.
struct SensorReading
{
    int sensor_id;
    double value;
    std::string unit;
    std::string timestamp;
    std::string nonce;
};

/// Serialize a reading to JSON bytes.
std::vector<uint8_t> serialize_reading(const SensorReading& reading);

/// Deserialize JSON bytes back to a reading.
SensorReading deserialize_reading(const std::vector<uint8_t>& data);

/// Serialize a reading to a CAN frame payload (8 bytes max).
/// Encodes sensor_id (2 bytes) + value as fixed-point (4 bytes) + unit code (1 byte) + flags (1 byte).
std::vector<uint8_t> serialize_to_can_frame(const SensorReading& reading);

/// Deserialize a CAN frame payload back to a reading.
SensorReading deserialize_from_can_frame(const std::vector<uint8_t>& frame_data);

/// Unit string to 1-byte code for CAN frames.
uint8_t unit_to_code(const std::string& unit);

/// 1-byte code back to unit string.
std::string code_to_unit(uint8_t code);

} // namespace sensorproto