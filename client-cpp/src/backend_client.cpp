#include "backend_client.hpp"
#include "hmac_signer.hpp"
#include "nonce_generator.hpp"

#include <cpr/cpr.h>
#include <nlohmann/json.hpp>
#include <stdexcept>
#include <utility>

using json = nlohmann::json;

BackendClient::BackendClient(std::string backend_url) : backend_url_(std::move(backend_url)) 
{}

bool BackendClient::check_health() 
{
    cpr::Response r = cpr::Get(cpr::Url{backend_url_ + "/health"});
    return r.status_code == 200;
}

SensorIdentity BackendClient::register_sensor(const std::string& name, const std::string& location) 
{
    json body = {
        {"name", name},
        {"location", location}
    };

    cpr::Response r = cpr::Post(
        cpr::Url{backend_url_ + "/sensors"},
        cpr::Header{{"Content-Type", "application/json"}},
        cpr::Body{body.dump()}
    );

    if (r.status_code != 201) 
    {
        throw std::runtime_error("sensor registration failed, status=" +
                                 std::to_string(r.status_code) +
                                 " body=" + r.text);
    }

    json response = json::parse(r.text);
    
    return SensorIdentity{response["id"], response["api_key"]};
}

bool BackendClient::submit_reading(const SensorIdentity& sensor, double value, const std::string& unit) 
{
    json body = {
        {"sensor_id", sensor.id},
        {"value", value},
        {"unit", unit}
    };

    std::string payload = body.dump();

    // Security: HMAC sign the payload with the API key
    HmacSigner signer(sensor.api_key);
    std::string nonce = NonceGenerator::generate_nonce();
    std::string ts = NonceGenerator::timestamp();

    // Sign: payload + nonce + timestamp
    std::string sign_input = payload + nonce + ts;
    std::string signature = signer.sign(sign_input);

    cpr::Response r = cpr::Post(
        cpr::Url{backend_url_ + "/readings"},
        cpr::Header{
            {"Content-Type", "application/json"},
            {"x-api-key", sensor.api_key},
            {"x-signature", signature},
            {"x-nonce", nonce},
            {"x-timestamp", ts}
        },
        cpr::Body{payload}
    );

    return r.status_code == 201;
}