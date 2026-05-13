#pragma once

#include <atomic>
#include <cstdint>

class MetricsCollector
{
public:
    static MetricsCollector& instance()
    {
        static MetricsCollector m;
        return m;
    }

    void record_success() { successes_++; }
    void record_failure() { failures_++; }
    void record_retry()   { retries_++; }

    uint64_t successes() const { return successes_; }
    uint64_t failures() const  { return failures_; }
    uint64_t retries() const   { return retries_; }

    void reset()
    {
        successes_ = 0;
        failures_ = 0;
        retries_ = 0;
    }

private:
    MetricsCollector() = default;
    std::atomic<uint64_t> successes_{0};
    std::atomic<uint64_t> failures_{0};
    std::atomic<uint64_t> retries_{0};
};
