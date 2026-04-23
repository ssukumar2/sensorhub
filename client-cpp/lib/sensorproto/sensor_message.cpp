#include "sensor_message.hpp"

#include <nlohmann/json.hpp>
#include <stdexcept>
#include <cmath>

using json = nlohmann::json;

namespace sensorproto {

std::vector<uint8_t> serialize(const SensorReading& reading)
{
    json j = {
        {"sensor_id", reading.sensor_id},
        {"value", reading.value},
        {"unit", reading.unit}
    };

    if (!reading.timestamp.empty())
        j["timestamp"] = reading.timestamp;

    if (!reading.nonce.empty())
        j["nonce"] = reading.nonce;

    std::string s = j.dump();
    return std::vector<uint8_t>(s.begin(), s.end());
}

SensorReading deserialize(const std::vector<uint8_t>& data)
{
    std::string s(data.begin(), data.end());
    json j = json::parse(s);

    SensorReading r;
    r.sensor_id = j.at("sensor_id").get<int>();
    r.value = j.at("value").get<double>();
    r.unit = j.at("unit").get<std::string>();

    if (j.contains("timestamp"))
        r.timestamp = j["timestamp"].get<std::string>();

    if (j.contains("nonce"))
        r.nonce = j["nonce"].get<std::string>();

    return r;
}

uint8_t unit_to_code(const std::string& unit)
{
    if (unit == "celsius")    return 0x01;
    if (unit == "fahrenheit") return 0x02;
    if (unit == "kelvin")     return 0x03;
    if (unit == "percent")    return 0x04;
    if (unit == "voltage")    return 0x06;
    if (unit == "ampere")     return 0x07;
    if (unit == "watt")       return 0x08;
    return 0x00;
}

std::string code_to_unit(uint8_t code)
{
    switch (code)
    {
        case 0x01: return "celsius";
        case 0x02: return "fahrenheit";
        case 0x03: return "kelvin";
        case 0x04: return "percent";
        case 0x06: return "voltage";
        case 0x07: return "ampere";
        case 0x08: return "watt";
        default:   return "unknown";
    }
}

std::vector<uint8_t> encode_can_frame(const SensorReading& reading)
{
    std::vector<uint8_t> frame(8, 0);

    uint16_t sid = static_cast<uint16_t>(reading.sensor_id);
    frame[0] = (sid >> 8) & 0xFF;
    frame[1] = sid & 0xFF;

    int32_t fixed_val = static_cast<int32_t>(std::round(reading.value * 100.0));
    frame[2] = (fixed_val >> 24) & 0xFF;
    frame[3] = (fixed_val >> 16) & 0xFF;
    frame[4] = (fixed_val >> 8) & 0xFF;
    frame[5] = fixed_val & 0xFF;

    frame[6] = unit_to_code(reading.unit);
    frame[7] = 0x00;

    return frame;
}

SensorReading decode_can_frame(const std::vector<uint8_t>& frame)
{
    if (frame.size() < 8)
        throw std::runtime_error("can frame too short");

    SensorReading r;
    r.sensor_id = (frame[0] << 8) | frame[1];

    int32_t fixed_val = (frame[2] << 24) | (frame[3] << 16) |
                        (frame[4] << 8) | frame[5];
    r.value = fixed_val / 100.0;
    r.unit = code_to_unit(frame[6]);

    return r;
}

} // namespace sensorproto