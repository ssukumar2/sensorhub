#include "can_transport.hpp"

#include <cstring>
#include <iostream>
#include <utility>

#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

CanTransport::CanTransport(std::string interface_name)
    : interface_name_(std::move(interface_name)) {}

CanTransport::~CanTransport() { close(); }

bool CanTransport::open()
{
    socket_fd_ = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (socket_fd_ < 0)
    {
        std::cerr << "failed to create CAN socket" << std::endl;
        return false;
    }

    struct ifreq ifr;
    std::strncpy(ifr.ifr_name, interface_name_.c_str(), IFNAMSIZ - 1);
    ifr.ifr_name[IFNAMSIZ - 1] = '\0';

    if (ioctl(socket_fd_, SIOCGIFINDEX, &ifr) < 0)
    {
        std::cerr << "CAN interface " << interface_name_
                  << " not found" << std::endl;
        ::close(socket_fd_);
        socket_fd_ = -1;
        return false;
    }

    struct sockaddr_can addr;
    std::memset(&addr, 0, sizeof(addr));
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;

    if (bind(socket_fd_, reinterpret_cast<struct sockaddr*>(&addr),
             sizeof(addr)) < 0)
    {
        std::cerr << "failed to bind CAN socket" << std::endl;
        ::close(socket_fd_);
        socket_fd_ = -1;
        return false;
    }

    return true;
}

void CanTransport::close()
{
    if (socket_fd_ >= 0)
    {
        ::close(socket_fd_);
        socket_fd_ = -1;
    }
}

bool CanTransport::send_frame(uint32_t can_id,
                               const std::vector<uint8_t>& data)
{
    if (socket_fd_ < 0 || data.size() > 8) return false;

    struct can_frame frame;
    std::memset(&frame, 0, sizeof(frame));
    frame.can_id = can_id;
    frame.can_dlc = static_cast<uint8_t>(data.size());
    std::memcpy(frame.data, data.data(), data.size());

    return write(socket_fd_, &frame, sizeof(frame)) == sizeof(frame);
}

bool CanTransport::receive_frame(uint32_t& can_id,
                                  std::vector<uint8_t>& data)
{
    if (socket_fd_ < 0) return false;

    struct can_frame frame;
    if (read(socket_fd_, &frame, sizeof(frame)) != sizeof(frame))
        return false;

    can_id = frame.can_id;
    data.assign(frame.data, frame.data + frame.can_dlc);
    return true;
}