#include "mqtt_client.hpp"

#include <nlohmann/json.hpp>

#include <chrono>
#include <iostream>
#include <thread>
#include <utility>

using json = nlohmann::json;

MqttClient::MqttClient(std::string broker_url, std::string client_id) : broker_url_(std::move(broker_url)), 
                       client_id_(std::move(client_id)) 
{
    MQTTAsync_create(&client_, broker_url_.c_str(), client_id_.c_str(),
                     MQTTCLIENT_PERSISTENCE_NONE, nullptr);
}

MqttClient::~MqttClient() 
{
    disconnect();
    if (client_) 
    {
        MQTTAsync_destroy(&client_);
    }
}

bool MqttClient::connect() 
{
    MQTTAsync_connectOptions opts = MQTTAsync_connectOptions_initializer;
    opts.keepAliveInterval = 20;
    opts.cleansession = 1;

    int rc = MQTTAsync_connect(client_, &opts);
    if (rc != MQTTASYNC_SUCCESS) 
    {
        std::cerr << "mqtt connect failed, rc=" << rc << std::endl;
        return false;
    }

    // Simple wait loop for connection (async API normally uses callbacks,
    // we poll the connected state for simplicity).
    for (int i = 0; i < 50; ++i) 
    {
        if (MQTTAsync_isConnected(client_)) 
        {
            connected_ = true;
            return true;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    std::cerr << "mqtt connect timed out" << std::endl;
    return false;
}

void MqttClient::disconnect() 
{
    if (client_ && MQTTAsync_isConnected(client_)) 
    {
        MQTTAsync_disconnectOptions opts = MQTTAsync_disconnectOptions_initializer;
        opts.timeout = 1000;
        MQTTAsync_disconnect(client_, &opts);
    }
    connected_ = false;
}

bool MqttClient::publish_reading(int sensor_id, double value, const std::string& unit) 
{
    if (!MQTTAsync_isConnected(client_)) 
    {
        std::cerr << "mqtt not connected" << std::endl;
        return false;
    }

    json payload = 
    {
        {"value", value},
        {"unit", unit}
    };

    std::string payload_str = payload.dump();
    std::string topic = "sensorhub/sensors/" + std::to_string(sensor_id) + "/readings";

    MQTTAsync_message msg = MQTTAsync_message_initializer;
    msg.payload = (void*)payload_str.c_str();
    msg.payloadlen = static_cast<int>(payload_str.size());
    msg.qos = 1;
    msg.retained = 0;

    int rc = MQTTAsync_sendMessage(client_, topic.c_str(), &msg, nullptr);
    return rc == MQTTASYNC_SUCCESS;
}