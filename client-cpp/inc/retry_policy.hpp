#pragma once

#include <chrono>
#include <functional>
#include <thread>

/// Simple exponential-backoff retry helper for transient HTTP failures.
///
/// Retries when the supplied predicate returns false (e.g. status != 201).
/// Backoff doubles each attempt up to max_delay_ms.
class RetryPolicy
{
public:
    RetryPolicy(int max_attempts = 3,
                int initial_delay_ms = 200,
                int max_delay_ms = 2000)
        : max_attempts_(max_attempts),
          initial_delay_ms_(initial_delay_ms),
          max_delay_ms_(max_delay_ms) {}

    /// Run `op` up to max_attempts times. Returns true if any attempt succeeded.
    bool run(const std::function<bool()>& op) const
    {
        int delay = initial_delay_ms_;
        for (int attempt = 0; attempt < max_attempts_; ++attempt)
        {
            if (op()) return true;
            if (attempt + 1 < max_attempts_)
            {
                std::this_thread::sleep_for(std::chrono::milliseconds(delay));
                delay = std::min(delay * 2, max_delay_ms_);
            }
        }
        return false;
    }

private:
    int max_attempts_;
    int initial_delay_ms_;
    int max_delay_ms_;
};
