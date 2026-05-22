#pragma once

#include <string>
#include <vector>

struct PendingCommand
{
    std::string id;
    std::string type;
    std::string payload_json;
};

class CommandClient
{
public:
    explicit CommandClient(std::string backend_url);

    std::vector<PendingCommand> poll(int sensor_id, const std::string& api_key);
    bool ack(const std::string& cmd_id, const std::string& api_key, const std::string& result = "");

private:
    std::string backend_url_;
};
