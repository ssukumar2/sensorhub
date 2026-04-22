#pragma once

#include <cstdint>
#include <string>
#include <vector>

class CanTransport
{
public:
    explicit CanTransport(std::string interface_name = "vcan0");
    ~CanTransport();

    CanTransport(const CanTransport&) = delete;
    CanTransport& operator=(const CanTransport&) = delete;

    bool open();
    void close();
    bool send_frame(uint32_t can_id, const std::vector<uint8_t>& data);
    bool receive_frame(uint32_t& can_id, std::vector<uint8_t>& data);

private:
    std::string interface_name_;
    int socket_fd_{-1};
};