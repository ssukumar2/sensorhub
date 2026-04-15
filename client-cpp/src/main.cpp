#include <iostream>
#include <cpr/cpr.h>
#include <nlohmann/json.hpp>
#include <string>
#include <chrono>
#include <random>
#include <thread>
#include <csignal>

using json = nlohmann::json;

// Global flag so Ctrl+C can stop the loop cleanly
volatile std::sig_atomic_t keep_running = 1;

void handle_sigint(int) 
{
    keep_running = 0;
}

int main() 
{
     std::signal(SIGINT, handle_sigint);
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
    const int interval_seconds = 5;

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

    //json reg_body = 
    json reg_body = 
    {
        {"name", "cpp-sensor-01"},
        {"location", "lab"}
    };

    cpr::Response reg = cpr::Post(
        cpr::Url{backend_url + "/sensors"},
        cpr::Header{{"Content-Type", "application/json"}},
        //cpr::Body{body.dump()}
        cpr::Body{reg_body.dump()}
    );

    // std::cout << "status: " << reg.status_code << std::endl;
    // std::cout << "response: " << reg.text << std::endl;

    // if (reg.status_code != 201) 
    // {
    //     std::cerr << "sensor registration failed" << std::endl;
    //     return 1;
    // }

    // // Step C: parse the response and extract the api key
    // json response = json::parse(reg.text);
    // int sensor_id = response["id"];
    // std::string api_key = response["api_key"];

    // std::cout << "sensor registered successfully" << std::endl;
    // std::cout << "  id: " << sensor_id << std::endl;
    // std::cout << "  api_key: " << api_key << std::endl;

    // return 0;

    if (reg.status_code != 201)
    {
        std::cerr << "registration failed, status=" << reg.status_code
                  << " body=" << reg.text << std::endl;
        return 1;
    }

    json reg_response = json::parse(reg.text);
    int sensor_id = reg_response["id"];
    std::string api_key = reg_response["api_key"];
    std::cout << "sensor registered. id=" << sensor_id << std::endl;
              //<< " api_key=" << api_key.substr(0, 8) << "..." << std::endl;

    
    // std::cout << "sending reading..." << std::endl;

    // Random number generator for fake temperature readings

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_real_distribution<double> temp_dist(18.0, 28.0);

    // Loop until Ctrl+C
    std::cout << "starting reading loop (press Ctrl+C to stop)..." << std::endl;
    int reading_count = 0;

    while (keep_running) 
    {
        double temperature = temp_dist(gen);

    json reading_body = 
    {
        {"sensor_id", sensor_id},
        // {"value", 22.5},
        {"value", temperature},
        {"unit", "celsius"}
    };

    cpr::Response reading = cpr::Post(
        cpr::Url{backend_url + "/readings"},
        cpr::Header{
            {"Content-Type", "application/json"},
            {"x-api-key", api_key}
        },
        cpr::Body{reading_body.dump()}
    );

    // std::cout << "status: " << reading.status_code << std::endl;
    // std::cout << "response: " << reading.text << std::endl;

    // if (reading.status_code != 201) 
    // {
    //     std::cerr << "reading submission failed" << std::endl;
    //     return 1;
    // }

    // std::cout << "reading submitted successfully" << std::endl;

    if (reading.status_code == 201) 
    {
            reading_count++;
            std::cout << "[" << reading_count << "] sent "
                      << temperature << " celsius, status=201" << std::endl;
    } 
    else 
    {
            std::cerr << "failed to send reading, status=" << reading.status_code
                      << " body=" << reading.text << std::endl;
    }

        // Sleep, but wake up if Ctrl+C was pressed
        for (int i = 0; i < interval_seconds && keep_running; i++) 
        {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }

    std::cout << "\nstopped after " << reading_count
              << " readings. bye." << std::endl;

    return 0;
}

