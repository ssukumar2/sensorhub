#pragma once

#include "backend_client.hpp"
#include "logger.hpp"
#include "metrics.hpp"

#include <mutex>
#include <vector>

/// Accumulates readings and flushes them in bulk to /readings/batch.
/// Useful when readings come fast and individual HTTP posts would be wasteful.
class BatchAccumulator
{
public:
    BatchAccumulator(BackendClient& client, const SensorIdentity& sensor,
                     size_t batch_size = 10)
        : client_(client), sensor_(sensor), batch_size_(batch_size) {}

    void add(double value, const std::string& unit)
    {
        std::lock_guard<std::mutex> g(mutex_);
        items_.push_back({value, unit});
        if (items_.size() >= batch_size_)
            flush_locked();
    }

    void flush()
    {
        std::lock_guard<std::mutex> g(mutex_);
        flush_locked();
    }

    size_t pending() const
    {
        std::lock_guard<std::mutex> g(mutex_);
        return items_.size();
    }

private:
    BackendClient& client_;
    SensorIdentity sensor_;
    size_t batch_size_;
    std::vector<BackendClient::ReadingItem> items_;
    mutable std::mutex mutex_;

    void flush_locked()
    {
        if (items_.empty()) return;
        bool ok = client_.submit_batch(sensor_, items_);
        if (ok)
        {
            for (size_t i = 0; i < items_.size(); ++i)
                MetricsCollector::instance().record_success();
            Logger::instance().info("flushed batch of " + std::to_string(items_.size()));
        }
        else
        {
            for (size_t i = 0; i < items_.size(); ++i)
                MetricsCollector::instance().record_failure();
            Logger::instance().error("batch flush failed (" + std::to_string(items_.size()) + " items)");
        }
        items_.clear();
    }
};
