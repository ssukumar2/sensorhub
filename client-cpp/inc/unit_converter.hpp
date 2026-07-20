#pragma once

#include <stdexcept>
#include <string>

/// Stateless unit conversion helpers for common IoT sensor types.
class UnitConverter
{
public:
    static double celsius_to_fahrenheit(double c) { return c * 9.0 / 5.0 + 32.0; }
    static double fahrenheit_to_celsius(double f) { return (f - 32.0) * 5.0 / 9.0; }
    static double celsius_to_kelvin(double c)     { return c + 273.15; }
    static double kelvin_to_celsius(double k)     { return k - 273.15; }
    static double hpa_to_psi(double hpa)          { return hpa * 0.0145038; }
    static double psi_to_hpa(double psi)          { return psi / 0.0145038; }
    static double volts_to_mv(double v)           { return v * 1000.0; }
    static double mv_to_volts(double mv)          { return mv / 1000.0; }

    /// Convert value from `from_unit` to `to_unit`. Throws on unknown pair.
    static double convert(double value, const std::string& from, const std::string& to)
    {
        if (from == to) return value;
        if (from == "celsius"    && to == "fahrenheit") return celsius_to_fahrenheit(value);
        if (from == "fahrenheit" && to == "celsius")    return fahrenheit_to_celsius(value);
        if (from == "celsius"    && to == "kelvin")     return celsius_to_kelvin(value);
        if (from == "kelvin"     && to == "celsius")    return kelvin_to_celsius(value);
        if (from == "hpa"        && to == "psi")        return hpa_to_psi(value);
        if (from == "psi"        && to == "hpa")        return psi_to_hpa(value);
        if (from == "v"          && to == "mv")         return volts_to_mv(value);
        if (from == "mv"         && to == "v")          return mv_to_volts(value);
        throw std::invalid_argument("unknown unit pair: " + from + " -> " + to);
    }
};
