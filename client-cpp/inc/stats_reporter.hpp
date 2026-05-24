#pragma once

#include "logger.hpp"
#include "metrics.hpp"

#include <atomic>
#include <chrono>
#include <thread>

/// Background thread that logs current metrics every interval_seconds.
class StatsReporter
{
public:
    StatsReporter(int interval_seconds = 60) : interval_(interval_seconds) {}

    ~StatsReporter() { stop(); }

    void start()
    {
        running_ = true;
        worker_ = std::thread([this]() {
            while (running_)
            {
                for (int i = 0; i < interval_ && running_; ++i)
                    std::this_thread::sleep_for(std::chrono::seconds(1));
                if (!running_) break;
                auto& m = MetricsCollector::instance();
                Logger::instance().info(
                    "stats: success=" + std::to_string(m.successes()) +
                    " fail=" + std::to_string(m.failures()) +
                    " retries=" + std::to_string(m.retries())
                );
            }
        });
    }

    void stop()
    {
        running_ = false;
        if (worker_.joinable())
            worker_.join();
    }

private:
    int interval_;
    std::atomic<bool> running_{false};
    std::thread worker_;
};
