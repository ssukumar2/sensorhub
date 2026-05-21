#include "firmware_client.hpp"

#include <cpr/cpr.h>
#include <nlohmann/json.hpp>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <openssl/sha.h>
#include <utility>

using json = nlohmann::json;

FirmwareClient::FirmwareClient(std::string backend_url) : backend_url_(std::move(backend_url)) {}

bool FirmwareClient::report(int sensor_id, const std::string& api_key,
                            const std::string& version, const std::string& build_date)
{
    cpr::Response r = cpr::Post(
        cpr::Url{backend_url_ + "/firmware/report"},
        cpr::Header{{"x-api-key", api_key}},
        cpr::Parameters{
            {"sensor_id", std::to_string(sensor_id)},
            {"version", version},
            {"build_date", build_date},
        }
    );
    return r.status_code == 200;
}

FirmwareCheckResult FirmwareClient::check(const std::string& current_version)
{
    FirmwareCheckResult result;
    result.current = current_version;
    cpr::Response r = cpr::Get(
        cpr::Url{backend_url_ + "/firmware/check"},
        cpr::Parameters{{"current_version", current_version}}
    );
    if (r.status_code != 200) return result;
    try {
        auto j = json::parse(r.text);
        result.update_available = j.value("update_available", false);
        result.latest = j.value("latest", "");
        result.url = j.value("url", "");
    } catch (...) {}
    return result;
}

bool FirmwareClient::download(const std::string& version, const std::string& out_path, std::string& expected_sha)
{
    cpr::Response r = cpr::Get(cpr::Url{backend_url_ + "/firmware/download/" + version});
    if (r.status_code != 200) return false;
    std::ofstream out(out_path, std::ios::binary);
    if (!out) return false;
    out.write(r.text.data(), r.text.size());
    out.close();
    auto it = r.header.find("x-sha256");
    if (it != r.header.end()) expected_sha = it->second;
    return true;
}

std::string FirmwareClient::sha256_of_file(const std::string& path)
{
    std::ifstream in(path, std::ios::binary);
    if (!in) return "";
    SHA256_CTX ctx;
    SHA256_Init(&ctx);
    char buf[8192];
    while (in.read(buf, sizeof(buf)) || in.gcount())
        SHA256_Update(&ctx, buf, in.gcount());
    unsigned char digest[SHA256_DIGEST_LENGTH];
    SHA256_Final(digest, &ctx);
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (int i = 0; i < SHA256_DIGEST_LENGTH; ++i)
        oss << std::setw(2) << static_cast<int>(digest[i]);
    return oss.str();
}
