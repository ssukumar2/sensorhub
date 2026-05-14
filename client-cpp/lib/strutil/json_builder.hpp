#pragma once

#include <sstream>
#include <string>

/// Minimal compact JSON object builder for request payloads.
/// Not a general parser - just enough to build flat objects predictably.
class JsonBuilder
{
public:
    JsonBuilder& add(const std::string& key, const std::string& value)
    {
        sep();
        oss_ << '"' << key << "\":\"" << value << '"';
        return *this;
    }

    JsonBuilder& add(const std::string& key, double value)
    {
        sep();
        oss_ << '"' << key << "\":" << value;
        return *this;
    }

    JsonBuilder& add(const std::string& key, int value)
    {
        sep();
        oss_ << '"' << key << "\":" << value;
        return *this;
    }

    std::string build() const
    {
        return "{" + oss_.str() + "}";
    }

private:
    std::ostringstream oss_;
    bool first_ = true;

    void sep()
    {
        if (!first_) oss_ << ',';
        first_ = false;
    }
};
