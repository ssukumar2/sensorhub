#pragma once

#include <string>

struct ClientConfig
{
    std::string backend_url = "http://localhost:8000";
    std::string mqtt_url = "tcp://localhost:1883";
    std::string can_iface = "vcan0";
    std::string sensor_name = "cpp-sensor-01";
    std::string sensor_location = "lab";
    std::string mode = "http";
    int interval_seconds = 5;
    std::string log_level = "info";

    static ClientConfig from_args(int argc, char* argv[]);
};
