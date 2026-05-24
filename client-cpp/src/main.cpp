#include "config.hpp"
#include "logger.hpp"
#include "signal_handler.hpp"
#include "metrics.hpp"
#include "stats_reporter.hpp"
#include "backend_client.hpp"
#include "firmware_client.hpp"
#include "firmware_updater.hpp"
#include "command_client.hpp"
#include "retry_policy.hpp"
#include "health_checker.hpp"
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



int main(int argc, char* argv[]) 
{
    SignalHandler::instance().install();

    for (int i = 1; i < argc; ++i)
    {
        std::string a = argv[i];
        if (a == "--help" || a == "-h")
        {
            std::cout << "usage: sensor_client [options]\n"
                      << "  --mode=http|mqtt|can     transport (default http)\n"
                      << "  --backend=URL            backend base url\n"
                      << "  --mqtt=URL               mqtt broker url\n"
                      << "  --can=IFACE              can interface (default vcan0)\n"
                      << "  --name=NAME              sensor name\n"
                      << "  --location=LOC           sensor location\n"
                      << "  --interval=N             seconds between readings\n"
                      << "  --log-level=debug|info|warn|error\n"
                      << "  --help                   this message\n";
            return 0;
        }
    }
    ClientConfig cfg = ClientConfig::from_args(argc, argv);
    if (cfg.log_level == "debug") Logger::instance().set_level(Logger::Level::Debug);
    else if (cfg.log_level == "warn") Logger::instance().set_level(Logger::Level::Warn);
    else if (cfg.log_level == "error") Logger::instance().set_level(Logger::Level::Error);
    Logger::instance().info("mode: " + cfg.mode);

    // Always register the sensor via HTTP (we need an API key either way
    // to identify it, and MQTT version uses sensor_id only).

    BackendClient http(cfg.backend_url);

    {
        int attempts = 0;
        const int max_attempts = 30;
        while (!http.check_health())
        {
            ++attempts;
            if (attempts >= max_attempts)
            {
                Logger::instance().error("backend not reachable at " + cfg.backend_url + " after " + std::to_string(max_attempts) + " attempts");
                return 1;
            }
            Logger::instance().warn("waiting for backend... attempt " + std::to_string(attempts));
            std::this_thread::sleep_for(std::chrono::seconds(2));
        }
    }


    SensorIdentity sensor;

    try 
    {
        sensor = http.register_sensor(cfg.sensor_name, cfg.sensor_location);
    } 
    catch (const std::exception& e) 
    {
        Logger::instance().error(std::string("registration failed: ") + e.what());
        return 1;
    }

    Logger::instance().info("sensor registered, id=" + std::to_string(sensor.id));

    HealthChecker health_checker(http, 30);
    if (cfg.health_check)
        health_checker.start();

    StatsReporter stats(60);
    stats.start();

    const std::string current_version = "0.1.0";
    FirmwareClient firmware(cfg.backend_url);
    firmware.report(sensor.id, sensor.api_key, current_version, __DATE__);

    FirmwareUpdater updater(firmware);
    auto upd = updater.run_once(current_version);
    if (upd.verified)
        Logger::instance().info("ready to flash: " + upd.path);
    else if (!upd.error.empty())
        Logger::instance().warn("firmware update skipped: " + upd.error);

    // Random temperature
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<double> temp_dist(18.0, 28.0);
    int count = 0;
    const int interval = cfg.interval_seconds;

    CommandClient commands(cfg.backend_url);

    if (cfg.mode == "mqtt") 
    {
        MqttClient mqtt(cfg.mqtt_url, "sensorhub-cpp-client");
        if (!mqtt.connect()) 
        {
            Logger::instance().error("mqtt connect failed");
            return 1;
        }

        Logger::instance().info("mqtt connected, starting loop");

        while (SignalHandler::instance().keep_running()) 
        {
            double t = temp_dist(gen);
            if (mqtt.publish_reading(sensor.id, t, "celsius")) 
            {
                ++count;
                MetricsCollector::instance().record_success();
                std::cout << "[" << count << "] mqtt published " << t << " c" << std::endl;
            } 
            else 
            {
                MetricsCollector::instance().record_failure();
                Logger::instance().error("mqtt publish failed");
            }
            for (int i = 0; i < interval && SignalHandler::instance().keep_running(); ++i) 
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

        while (SignalHandler::instance().keep_running())
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
                MetricsCollector::instance().record_success();
                std::cout << "[" << count << "] CAN 0x" << std::hex << can_id
                          << std::dec << " " << t << " c" << std::endl;
            }
            else
            {
                MetricsCollector::instance().record_failure();
                std::cerr << "CAN send failed" << std::endl;
            }

            for (int i = 0; i < interval && SignalHandler::instance().keep_running(); ++i)
                std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }
    else 
    {
        Logger::instance().info("http mode, starting loop");
        auto poll_and_handle = [&]() {
            auto pending = commands.poll(sensor.id, sensor.api_key);
            for (const auto& c : pending)
            {
                Logger::instance().info("command received: " + c.type + " (id=" + c.id + ")");
                commands.ack(c.id, sensor.api_key, "received");
            }
        };
        while (SignalHandler::instance().keep_running()) 
        {
            double t = temp_dist(gen);
            poll_and_handle();
            RetryPolicy retry(3, 200, 2000);
            bool ok = retry.run([&]() { return http.submit_reading(sensor, t, "celsius"); });
            if (ok) 
            {
                ++count;
                MetricsCollector::instance().record_success();
                std::cout << "[" << count << "] http sent " << t << " c" << std::endl;
            } 
            else 
            {
                MetricsCollector::instance().record_failure();
                Logger::instance().error("http send failed after retries");
            }
            for (int i = 0; i < interval && SignalHandler::instance().keep_running(); ++i) 
            {
                std::this_thread::sleep_for(std::chrono::seconds(1));
            }
        }
    }

    health_checker.stop();
    stats.stop();
    auto& m = MetricsCollector::instance();
    std::cout << "\nstopped after " << count << " readings"
              << " (success=" << m.successes()
              << " fail=" << m.failures()
              << " backend_healthy=" << (health_checker.is_healthy() ? "yes" : "no")
              << ")" << std::endl;
    return 0;
}