#include "config.hpp"
#include "backend_client.hpp"
#include "retry_policy.hpp"
#include "mqtt_client.hpp"

#include "can_transport.hpp"
#include "sensor_message.hpp"

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

    ClientConfig cfg = ClientConfig::from_args(argc, argv);
    std::cout << "mode: " << cfg.mode << std::endl;

    // Always register the sensor via HTTP (we need an API key either way
    // to identify it, and MQTT version uses sensor_id only).

    BackendClient http(cfg.backend_url);

    if (!http.check_health()) 
    {
        std::cerr << "backend not reachable at " << cfg.backend_url << std::endl;
        return 1;
    }


    SensorIdentity sensor;

    try 
    {
        sensor = http.register_sensor(cfg.sensor_name, cfg.sensor_location);
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
    const int interval = cfg.interval_seconds;

    if (cfg.mode == "mqtt") 
    {
        MqttClient mqtt(cfg.mqtt_url, "sensorhub-cpp-client");
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
    else if (cfg.mode == "can")
    {
        CanTransport can(cfg.can_iface);
        if (!can.open())
        {
            std::cerr << "failed to open " << cfg.can_iface << std::endl;
            return 1;
        }
        std::cout << "CAN mode on vcan0. starting loop..." << std::endl;

        while (keep_running)
        {
            double t = temp_dist(gen);
            sensorproto::SensorReading reading;
            reading.sensor_id = sensor.id;
            reading.value = t;
            reading.unit = "celsius";

            auto frame_data = sensorproto::encode_can_frame(reading);
            uint32_t can_id = 0x100 + static_cast<uint32_t>(sensor.id);

            if (can.send_frame(can_id, frame_data))
            {
                ++count;
                std::cout << "[" << count << "] CAN 0x" << std::hex << can_id
                          << std::dec << " " << t << " c" << std::endl;
            }
            else
            {
                std::cerr << "CAN send failed" << std::endl;
            }

            for (int i = 0; i < interval && keep_running; ++i)
                std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }
    else 
    {
        std::cout << "http mode. starting loop..." << std::endl;
        while (keep_running) 
        {
            double t = temp_dist(gen);
            RetryPolicy retry(3, 200, 2000);
            bool ok = retry.run([&]() { return http.submit_reading(sensor, t, "celsius"); });
            if (ok) 
            {
                ++count;
                std::cout << "[" << count << "] http sent " << t << " c" << std::endl;
            } 
            else 
            {
                std::cerr << "http send failed after retries" << std::endl;
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