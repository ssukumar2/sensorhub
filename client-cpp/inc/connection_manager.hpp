#pragma once

#include "logger.hpp"

#include <atomic>
#include <chrono>
#include <thread>

/// Manages connection lifecycle: connect, monitor, reconnect on failure.
class ConnectionManager
{
public:
    ConnectionManager(int max_retries = 5, int retry_interval_sec = 5)
        : max_retries_(max_retries), retry_interval_(retry_interval_sec) {}

    ~ConnectionManager() { disconnect(); }

    void connect(const std::string& backend_url)
    {
        backend_url_ = backend_url;
        connected_ = true;
        Logger::instance().info("connected to " + backend_url);
    }

    void disconnect()
    {
        connected_ = false;
        Logger::instance().info("disconnected");
    }

    bool is_connected() const { return connected_; }

    bool ensure_connected(std::function<bool()> health_check)
    {
        if (connected_ && health_check())
            return true;

        int attempt = 0;
        while (attempt < max_retries_)
        {
            Logger::instance().warn("reconnect attempt " + std::to_string(attempt + 1) + "/" + std::to_string(max_retries_));
            std::this_thread::sleep_for(std::chrono::seconds(retry_interval_));
            if (health_check())
            {
                connected_ = true;
                Logger::instance().info("reconnected to " + backend_url_);
                return true;
            }
            ++attempt;
        }
        connected_ = false;
        Logger::instance().error("failed to reconnect after " + std::to_string(max_retries_) + " attempts");
        return false;
    }

private:
    std::string backend_url_;
    std::atomic<bool> connected_{false};
    int max_retries_;
    int retry_interval_;
};
