#pragma once

#include <stdexcept>
#include <vector>

/// Simple moving average filter for smoothing noisy sensor readings.
/// Useful before submission to reduce backend noise.
class MovingAverage
{
public:
    explicit MovingAverage(size_t window)
        : window_(window)
    {
        if (window < 1)
            throw std::invalid_argument("window must be >= 1");
        buf_.reserve(window);
    }

    void push(double value)
    {
        if (buf_.size() < window_)
            buf_.push_back(value);
        else
        {
            buf_[head_] = value;
            head_ = (head_ + 1) % window_;
        }
    }

    double value() const
    {
        if (buf_.empty()) return 0.0;
        double sum = 0.0;
        for (double v : buf_) sum += v;
        return sum / buf_.size();
    }

    bool ready() const { return buf_.size() >= window_; }

    void reset() { buf_.clear(); head_ = 0; }

private:
    size_t window_;
    size_t head_ = 0;
    std::vector<double> buf_;
};
