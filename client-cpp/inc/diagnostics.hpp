#pragma once

#include "metrics.hpp"
#include "logger.hpp"
#include "config.hpp"

#include <string>

/// Dumps full client diagnostic state to the logger.
/// Call on SIGUSR1 or from a debug endpoint.
class DiagnosticsReporter
{
public:
    static void dump(const ClientConfig& cfg)
    {
        auto& m = MetricsCollector::instance();
        Logger::instance().info("=== DIAGNOSTICS ===");
        Logger::instance().info("backend:    " + cfg.backend_url);
        Logger::instance().info("mode:       " + cfg.mode);
        Logger::instance().info("interval:   " + std::to_string(cfg.interval_seconds) + "s");
        Logger::instance().info("smooth:     " + std::to_string(cfg.smooth_window));
        Logger::instance().info("success:    " + std::to_string(m.successes()));
        Logger::instance().info("failures:   " + std::to_string(m.failures()));
        Logger::instance().info("retries:    " + std::to_string(m.retries()));
        Logger::instance().info("===================");
    }
};
