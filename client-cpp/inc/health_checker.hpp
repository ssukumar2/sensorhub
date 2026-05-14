#pragma once

#include "backend_client.hpp"
#include "logger.hpp"

#include <atomic>
#include <chrono>
#include <thread>

/// Background health monitor. Polls the backend periodically and
/// exposes the last known state. Stops cleanly on destruction.
class HealthChecker
{
public:
    HealthChecker(BackendClient& client, int interval_seconds = 30)
        : client_(client), interval_(interval_seconds) {}

    ~HealthChecker() { stop(); }

    void start()
    {
        running_ = true;
        worker_ = std::thread([this]() {
            while (running_)
            {
                bool ok = client_.check_health();
                healthy_ = ok;
                if (!ok)
                    Logger::instance().warn("backend health check failed");
                for (int i = 0; i < interval_ && running_; ++i)
                    std::this_thread::sleep_for(std::chrono::seconds(1));
            }
        });
    }

    void stop()
    {
        running_ = false;
        if (worker_.joinable())
            worker_.join();
    }

    bool is_healthy() const { return healthy_; }

private:
    BackendClient& client_;
    int interval_;
    std::atomic<bool> running_{false};
    std::atomic<bool> healthy_{true};
    std::thread worker_;
};
