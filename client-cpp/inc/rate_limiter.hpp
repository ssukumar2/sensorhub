#pragma once

#include <chrono>
#include <mutex>
#include <thread>

/// Simple sliding-window rate limiter. acquire() blocks until allowed.
class RateLimiter
{
public:
    RateLimiter(int max_per_second = 10) : interval_ms_(1000 / std::max(1, max_per_second)) {}

    void acquire()
    {
        std::lock_guard<std::mutex> g(mutex_);
        auto now = std::chrono::steady_clock::now();
        auto since = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_).count();
        if (since < interval_ms_)
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(interval_ms_ - since));
        }
        last_ = std::chrono::steady_clock::now();
    }

private:
    int interval_ms_;
    std::chrono::steady_clock::time_point last_ = std::chrono::steady_clock::now();
    std::mutex mutex_;
};
