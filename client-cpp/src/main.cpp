#include "backend_client.hpp"
#include "mqtt_client.hpp"

#include <chrono>
#include <csignal>
#include <cstring>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <thread>

volatile std::sig_atomic_t keep_running = 1;

void handle_sigint(int) {
    keep_running = 0;
}

int main(int argc, char* argv[]) 
{
    std::signal(SIGINT, handle_sigint);

    std::string backend_url = "http://localhost:8000";
    std::string mqtt_url = "tcp://localhost:1883";
    std::string mode = "http";  // "http" or "mqtt"

    // Simple arg parsing: --mode=mqtt, --backend=..., --mqtt=...
    for (int i = 1; i < argc; ++i) 
    {
        std::string arg = argv[i];
        if (arg.rfind("--mode=", 0) == 0) 
        {
            mode = arg.substr(7);
        } else if (arg.rfind("--backend=", 0) == 0) 
        {
            backend_url = arg.substr(10);
        } else if (arg.rfind("--mqtt=", 0) == 0) 
        {
            mqtt_url = arg.substr(7);
        }
    }
    std::cout << "mode: " << mode << std::endl;

    // Always register the sensor via HTTP (we need an API key either way
    // to identify it, and MQTT version uses sensor_id only).

    BackendClient http(backend_url);

    if (!http.check_health()) 
    {
        std::cerr << "backend not reachable at " << backend_url << std::endl;
        return 1;
    }


    SensorIdentity sensor;

    try 
    {
        sensor = http.register_sensor("cpp-sensor-01", "lab");
    } 
    catch (const std::exception& e) 
    {
        std::cerr << "registration failed: " << e.what() << std::endl;
        return 1;
    }

    std::cout << "sensor registered, id=" << sensor.id << std::endl;

    // Random temperature
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<double> temp_dist(18.0, 28.0);
    int count = 0;
    const int interval = 5;

    if (mode == "mqtt") 
    {
        MqttClient mqtt(mqtt_url, "sensorhub-cpp-client");
        if (!mqtt.connect()) 
        {
            std::cerr << "mqtt connect failed" << std::endl;
            return 1;
        }

        std::cout << "mqtt connected. starting loop..." << std::endl;

        while (keep_running) 
        {
            double t = temp_dist(gen);
            if (mqtt.publish_reading(sensor.id, t, "celsius")) 
            {
                ++count;
                std::cout << "[" << count << "] mqtt published " << t << " c" << std::endl;
            } 
            else 
            {
                std::cerr << "mqtt publish failed" << std::endl;
            }
            for (int i = 0; i < interval && keep_running; ++i) 
            {
                std::this_thread::sleep_for(std::chrono::seconds(1));
            }
        }
    } 
    else 
    {
        std::cout << "http mode. starting loop..." << std::endl;
        while (keep_running) 
        {
            double t = temp_dist(gen);
            if (http.submit_reading(sensor, t, "celsius")) 
            {
                ++count;
                std::cout << "[" << count << "] http sent " << t << " c" << std::endl;
            } 
            else 
            {
                std::cerr << "http send failed" << std::endl;
            }
            for (int i = 0; i < interval && keep_running; ++i) 
            {
                std::this_thread::sleep_for(std::chrono::seconds(1));
            }
        }
    }

    std::cout << "\nstopped after " << count << " readings" << std::endl;
    return 0;
}