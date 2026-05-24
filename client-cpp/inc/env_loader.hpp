#pragma once

#include <cstdlib>
#include <string>

/// Read environment variables with sensible fallbacks.
class EnvLoader
{
public:
    static std::string get(const std::string& key, const std::string& fallback = "")
    {
        const char* v = std::getenv(key.c_str());
        return (v && *v) ? std::string(v) : fallback;
    }

    static int get_int(const std::string& key, int fallback)
    {
        const char* v = std::getenv(key.c_str());
        if (!v || !*v) return fallback;
        try { return std::stoi(v); } catch (...) { return fallback; }
    }

    static bool get_bool(const std::string& key, bool fallback)
    {
        const char* v = std::getenv(key.c_str());
        if (!v || !*v) return fallback;
        std::string s(v);
        return s == "1" || s == "true" || s == "yes" || s == "TRUE";
    }
};
