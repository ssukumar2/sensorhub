#pragma once

#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <vector>

namespace bytebuf {

/// A simple byte buffer for building and reading binary messages.
class ByteBuffer
{
public:
    ByteBuffer() = default;

    explicit ByteBuffer(const std::vector<uint8_t>& data)
        : data_(data), read_pos_(0) {}

    /// Write a uint8.
    void write_u8(uint8_t val)
    {
        data_.push_back(val);
    }

    /// Write a uint16 in big-endian.
    void write_u16_be(uint16_t val)
    {
        data_.push_back((val >> 8) & 0xFF);
        data_.push_back(val & 0xFF);
    }

    /// Write a uint32 in big-endian.
    void write_u32_be(uint32_t val)
    {
        data_.push_back((val >> 24) & 0xFF);
        data_.push_back((val >> 16) & 0xFF);
        data_.push_back((val >> 8) & 0xFF);
        data_.push_back(val & 0xFF);
    }

    /// Write raw bytes.
    void write_bytes(const uint8_t* src, size_t len)
    {
        data_.insert(data_.end(), src, src + len);
    }

    /// Read a uint8.
    uint8_t read_u8()
    {
        check_readable(1);
        return data_[read_pos_++];
    }

    /// Read a uint16 in big-endian.
    uint16_t read_u16_be()
    {
        check_readable(2);
        uint16_t val = (static_cast<uint16_t>(data_[read_pos_]) << 8) |
                        data_[read_pos_ + 1];
        read_pos_ += 2;
        return val;
    }

    /// Read a uint32 in big-endian.
    uint32_t read_u32_be()
    {
        check_readable(4);
        uint32_t val = (static_cast<uint32_t>(data_[read_pos_]) << 24) |
                       (static_cast<uint32_t>(data_[read_pos_ + 1]) << 16) |
                       (static_cast<uint32_t>(data_[read_pos_ + 2]) << 8) |
                        data_[read_pos_ + 3];
        read_pos_ += 4;
        return val;
    }

    /// Get the internal data.
    const std::vector<uint8_t>& data() const { return data_; }

    /// Get remaining readable bytes.
    size_t remaining() const { return data_.size() - read_pos_; }

    /// Get total size.
    size_t size() const { return data_.size(); }

private:
    std::vector<uint8_t> data_;
    size_t read_pos_{0};

    void check_readable(size_t n)
    {
        if (read_pos_ + n > data_.size())
            throw std::runtime_error("bytebuf: read past end of buffer");
    }
};

} // namespace bytebuf