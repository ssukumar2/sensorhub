#include "command_client.hpp"

#include <cpr/cpr.h>
#include <nlohmann/json.hpp>
#include <utility>

using json = nlohmann::json;

CommandClient::CommandClient(std::string backend_url) : backend_url_(std::move(backend_url)) {}

std::vector<PendingCommand> CommandClient::poll(int sensor_id, const std::string& api_key)
{
    std::vector<PendingCommand> out;
    cpr::Response r = cpr::Get(
        cpr::Url{backend_url_ + "/sensors/" + std::to_string(sensor_id) + "/commands/pending"},
        cpr::Header{{"x-api-key", api_key}}
    );
    if (r.status_code != 200) return out;
    try {
        auto arr = json::parse(r.text);
        for (auto& item : arr)
        {
            PendingCommand c;
            c.id = item.value("id", "");
            c.type = item.value("type", "");
            c.payload_json = item.value("payload", json::object()).dump();
            out.push_back(c);
        }
    } catch (...) {}
    return out;
}

bool CommandClient::ack(const std::string& cmd_id, const std::string& api_key, const std::string& result)
{
    cpr::Response r = cpr::Post(
        cpr::Url{backend_url_ + "/commands/" + cmd_id + "/ack"},
        cpr::Header{{"x-api-key", api_key}},
        cpr::Parameters{{"result", result}}
    );
    return r.status_code == 200;
}
