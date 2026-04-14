#include <iostream>
#include <cpr/cpr.h>
#include <nlohmann/json.hpp>
#include <string>

using json = nlohmann::json;

int main() 
{
    //std::cout << "hello, sensorhub" << std::endl;
   
    // std::cout << "sending GET /health to backend..." << std::endl;

    // cpr::Response r = cpr::Get(cpr::Url{"http://localhost:8000/health"});

    // std::cout << "status code: " << r.status_code << std::endl;
    // std::cout << "response body: " << r.text << std::endl;

    // if (r.status_code == 200) 
    // {
    //     std::cout << "backend is healthy" << std::endl;
    //     return 0;
    // } 
    // else 
    // {
    //     std::cout << "backend unreachable or unhealthy" << std::endl;
    //     return 1;
    // }
    
    const std::string backend_url = "http://localhost:8000";

    // Step A: health check
    std::cout << "checking backend health..." << std::endl;
    cpr::Response health = cpr::Get(cpr::Url{backend_url + "/health"});
    if (health.status_code != 200) 
    {
        std::cerr << "backend not reachable, status=" << health.status_code << std::endl;
        return 1;
    }
    std::cout << "backend is healthy" << std::endl;

    // Step B: register a sensor
    std::cout << "registering sensor..." << std::endl;

    json body = 
    {
        {"name", "cpp-sensor-01"},
        {"location", "lab"}
    };

    cpr::Response reg = cpr::Post(
        cpr::Url{backend_url + "/sensors"},
        cpr::Header{{"Content-Type", "application/json"}},
        cpr::Body{body.dump()}
    );

    std::cout << "status: " << reg.status_code << std::endl;
    std::cout << "response: " << reg.text << std::endl;

    if (reg.status_code != 201) 
    {
        std::cerr << "sensor registration failed" << std::endl;
        return 1;
    }

    // Step C: parse the response and extract the api key
    json response = json::parse(reg.text);
    int sensor_id = response["id"];
    std::string api_key = response["api_key"];

    std::cout << "sensor registered successfully" << std::endl;
    std::cout << "  id: " << sensor_id << std::endl;
    std::cout << "  api_key: " << api_key << std::endl;

    return 0;


}