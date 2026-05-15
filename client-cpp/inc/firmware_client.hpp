#pragma once

#include <string>

struct FirmwareCheckResult
{
    bool update_available = false;
    std::string current;
    std::string latest;
    std::string url;
};

class FirmwareClient
{
public:
    explicit FirmwareClient(std::string backend_url);

    /// Report current device version to backend. Returns true on success.
    bool report(int sensor_id, const std::string& api_key,
                const std::string& version, const std::string& build_date = "");

    /// Ask backend whether a newer version is available.
    FirmwareCheckResult check(const std::string& current_version);

    /// Download firmware binary to a local path. Returns true on success.
    bool download(const std::string& version, const std::string& out_path);

private:
    std::string backend_url_;
};
