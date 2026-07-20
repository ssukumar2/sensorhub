#pragma once

#include "logger.hpp"

#include <atomic>
#include <chrono>
#include <functional>
#include <thread>

/// Software watchdog. If `kick()` is not called within timeout_seconds,
/// the callback fires (e.g. log an error, request stop, restart loop).
class Watchdog
{
public:
    Watchdog(int timeout_seconds, std::function<void()> on_timeout)
        : timeout_(timeout_seconds), callback_(std::move(on_timeout)) {}

    ~Watchdog() { stop(); }

    void start()
    {
        running_ = true;
        last_kick_ = std::chrono::steady_clock::now();
        worker_ = std::thread([this]() {
            while (running_)
            {
                std::this_thread::sleep_for(std::chrono::seconds(1));
                auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
                    std::chrono::steady_clock::now() - last_kick_.load()).count();
                if (elapsed >= timeout_)
                {
                    Logger::instance().error("watchdog triggered after " +
                                             std::to_string(elapsed) + "s");
                    callback_();
                }
            }
        });
    }

    void kick()
    {
        last_kick_ = std::chrono::steady_clock::now();
    }

    void stop()
    {
        running_ = false;
        if (worker_.joinable()) worker_.join();
    }

private:
    int timeout_;
    std::function<void()> callback_;
    std::atomic<bool> running_{false};
    std::atomic<std::chrono::steady_clock::time_point> last_kick_{
        std::chrono::steady_clock::now()};
    std::thread worker_;
};
