#pragma once

#include "firmware_client.hpp"
#include "logger.hpp"

#include <string>

/// Orchestrates the firmware update lifecycle: check, download, verify checksum.
/// Does NOT install (platform-specific) - returns success once verified binary
/// is on disk.
class FirmwareUpdater
{
public:
    FirmwareUpdater(FirmwareClient& client, std::string download_dir = "/tmp")
        : client_(client), dir_(std::move(download_dir)) {}

    struct Result
    {
        bool checked = false;
        bool downloaded = false;
        bool verified = false;
        std::string version;
        std::string path;
        std::string error;
    };

    /// Run one full update cycle for current_version. Returns Result.
    Result run_once(const std::string& current_version)
    {
        Result r;
        auto check = client_.check(current_version);
        r.checked = true;
        if (!check.update_available)
        {
            Logger::instance().info("firmware already up to date: " + current_version);
            return r;
        }

        r.version = check.latest;
        r.path = dir_ + "/firmware-" + check.latest + ".bin";
        std::string expected;
        if (!client_.download(check.latest, r.path, expected))
        {
            r.error = "download failed";
            Logger::instance().error(r.error);
            return r;
        }
        r.downloaded = true;

        std::string actual = FirmwareClient::sha256_of_file(r.path);
        if (expected.empty())
        {
            r.error = "no checksum from server";
            Logger::instance().warn(r.error);
            return r;
        }
        if (actual != expected)
        {
            r.error = "checksum mismatch: expected=" + expected + " actual=" + actual;
            Logger::instance().error(r.error);
            return r;
        }
        r.verified = true;
        Logger::instance().info("firmware downloaded and verified: " + r.path);
        return r;
    }

private:
    FirmwareClient& client_;
    std::string dir_;
};
