#include "config.hpp"

#include <string>

ClientConfig ClientConfig::from_args(int argc, char* argv[])
{
    ClientConfig c;
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
    }
    return c;
}
