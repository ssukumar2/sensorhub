#pragma once

#include <iostream>
#include <mutex>
#include <string>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>

class Logger
{
public:
    enum class Level { Debug, Info, Warn, Error };

    static Logger& instance()
    {
        static Logger l;
        return l;
    }

    void set_level(Level lvl) { level_ = lvl; }

    void log(Level lvl, const std::string& msg)
    {
        if (lvl < level_) return;
        std::lock_guard<std::mutex> g(mutex_);
        std::cout << timestamp() << " [" << level_name(lvl) << "] " << msg << std::endl;
    }

    void debug(const std::string& m) { log(Level::Debug, m); }
    void info(const std::string& m) { log(Level::Info, m); }
    void warn(const std::string& m) { log(Level::Warn, m); }
    void error(const std::string& m) { log(Level::Error, m); }

private:
    Logger() = default;
    Level level_ = Level::Info;
    std::mutex mutex_;

    static const char* level_name(Level l)
    {
        switch (l)
        {
            case Level::Debug: return "DEBUG";
            case Level::Info:  return "INFO";
            case Level::Warn:  return "WARN";
            case Level::Error: return "ERROR";
        }
        return "?";
    }

    static std::string timestamp()
    {
        auto now = std::chrono::system_clock::now();
        auto t = std::chrono::system_clock::to_time_t(now);
        std::tm tm_buf;
        localtime_r(&t, &tm_buf);
        std::ostringstream oss;
        oss << std::put_time(&tm_buf, "%H:%M:%S");
        return oss.str();
    }
};
