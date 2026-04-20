#include "sensor_message.hpp"

#include <nlohmann/json.hpp>
#include <stdexcept>

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

} // namespace sensorproto