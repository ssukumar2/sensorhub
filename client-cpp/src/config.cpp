#include "config.hpp"
#include "env_loader.hpp"

#include <string>

ClientConfig ClientConfig::from_args(int argc, char* argv[])
{
    ClientConfig c;
    c.backend_url = EnvLoader::get("SENSORHUB_BACKEND_URL", c.backend_url);
    c.mqtt_url = EnvLoader::get("SENSORHUB_MQTT_URL", c.mqtt_url);
    c.can_iface = EnvLoader::get("SENSORHUB_CAN_IFACE", c.can_iface);
    c.sensor_name = EnvLoader::get("SENSORHUB_SENSOR_NAME", c.sensor_name);
    c.sensor_location = EnvLoader::get("SENSORHUB_SENSOR_LOCATION", c.sensor_location);
    c.mode = EnvLoader::get("SENSORHUB_MODE", c.mode);
    c.interval_seconds = EnvLoader::get_int("SENSORHUB_INTERVAL", c.interval_seconds);
    c.log_level = EnvLoader::get("SENSORHUB_LOG_LEVEL", c.log_level);
    c.health_check = EnvLoader::get_bool("SENSORHUB_HEALTH_CHECK", c.health_check);
    for (int i = 1; i < argc; ++i)
    {
        std::string arg = argv[i];
        if (arg.rfind("--mode=", 0) == 0) c.mode = arg.substr(7);
        else if (arg.rfind("--backend=", 0) == 0) c.backend_url = arg.substr(10);
        else if (arg.rfind("--mqtt=", 0) == 0) c.mqtt_url = arg.substr(7);
        else if (arg.rfind("--can=", 0) == 0) c.can_iface = arg.substr(6);
        else if (arg.rfind("--name=", 0) == 0) c.sensor_name = arg.substr(7);
        else if (arg.rfind("--location=", 0) == 0) c.sensor_location = arg.substr(11);
        else if (arg.rfind("--interval=", 0) == 0) c.interval_seconds = std::stoi(arg.substr(11));
        else if (arg.rfind("--log-level=", 0) == 0) c.log_level = arg.substr(12);
        else if (arg == "--no-health-check") c.health_check = false;
        else if (arg.rfind("--smooth=", 0) == 0) c.smooth_window = std::stoi(arg.substr(9));
    }
    return c;
}
