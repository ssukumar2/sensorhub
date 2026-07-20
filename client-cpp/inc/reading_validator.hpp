#pragma once

#include "logger.hpp"
#include "sensor_config.hpp"

#include <cmath>
#include <string>

/// Validates a reading before it is submitted to the backend.
/// Rejects NaN, Inf, and out-of-plausible-range values.
class ReadingValidator
{
public:
    struct Result
    {
        bool valid = false;
        std::string reason;
    };

    static Result validate(double value, const SensorConfig& cfg)
    {
        if (std::isnan(value))
            return {false, "value is NaN"};
        if (std::isinf(value))
            return {false, "value is Inf"};
        if (!cfg.is_plausible(value))
            return {false, "value " + std::to_string(value) +
                    " outside plausible range [" +
                    std::to_string(cfg.min_plausible) + ", " +
                    std::to_string(cfg.max_plausible) + "]"};
        return {true, ""};
    }

    static bool check_and_log(double value, const SensorConfig& cfg)
    {
        auto r = validate(value, cfg);
        if (!r.valid)
            Logger::instance().warn("reading rejected: " + r.reason);
        return r.valid;
    }
};
