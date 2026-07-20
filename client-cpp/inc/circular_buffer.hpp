#pragma once

#include <vector>
#include <mutex>
#include <stdexcept>

/// Fixed-size circular (ring) buffer. Oldest entry is overwritten when full.
/// Thread-safe via internal mutex.
template <typename T>
class CircularBuffer
{
public:
    explicit CircularBuffer(size_t capacity)
        : buf_(capacity), capacity_(capacity) {}

    void push(const T& value)
    {
        std::lock_guard<std::mutex> g(mutex_);
        buf_[head_] = value;
        head_ = (head_ + 1) % capacity_;
        if (size_ < capacity_) ++size_;
    }

    T latest() const
    {
        std::lock_guard<std::mutex> g(mutex_);
        if (size_ == 0) throw std::underflow_error("buffer is empty");
        size_t idx = (head_ + capacity_ - 1) % capacity_;
        return buf_[idx];
    }

    size_t size() const
    {
        std::lock_guard<std::mutex> g(mutex_);
        return size_;
    }

    bool empty() const { return size() == 0; }

    std::vector<T> to_vector() const
    {
        std::lock_guard<std::mutex> g(mutex_);
        std::vector<T> out;
        out.reserve(size_);
        for (size_t i = 0; i < size_; ++i)
            out.push_back(buf_[(head_ + capacity_ - size_ + i) % capacity_]);
        return out;
    }

private:
    std::vector<T> buf_;
    size_t capacity_;
    size_t head_ = 0;
    size_t size_ = 0;
    mutable std::mutex mutex_;
};
