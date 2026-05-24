#pragma once

#include <atomic>
#include <csignal>

/// Global SIGINT/SIGTERM handler. Tests `keep_running()` from main loop.
class SignalHandler
{
public:
    static SignalHandler& instance()
    {
        static SignalHandler h;
        return h;
    }

    void install()
    {
        std::signal(SIGINT, &SignalHandler::handle);
        std::signal(SIGTERM, &SignalHandler::handle);
    }

    bool keep_running() const { return running_; }

    void request_stop() { running_ = false; }

private:
    static void handle(int) { instance().running_ = false; }
    std::atomic<bool> running_{true};
};
