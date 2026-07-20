#pragma once

#include <string>

/// Runtime configuration for a single sensor channel.
/// Decouples what a sensor measures from how the client is configured.
struct SensorConfig
{
    std::string unit = "celsius";
    double min_plausible = -273.15;  // absolute zero — reject anything below
    double max_plausible = 1000.0;   // reject obvious outliers
    int decimals = 2;                // rounding precision for reported values

    bool is_plausible(double value) const
    {
        return value >= min_plausible && value <= max_plausible;
    }

    double round_to(double value) const
    {
        double factor = 1.0;
        for (int i = 0; i < decimals; ++i) factor *= 10.0;
        return static_cast<int>(value * factor + 0.5) / factor;
    }
};
