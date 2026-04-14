#include <iostream>
#include <cpr/cpr.h>

int main() 
{
    //std::cout << "hello, sensorhub" << std::endl;
   
    std::cout << "sending GET /health to backend..." << std::endl;

    cpr::Response r = cpr::Get(cpr::Url{"http://localhost:8000/health"});

    std::cout << "status code: " << r.status_code << std::endl;
    std::cout << "response body: " << r.text << std::endl;

    if (r.status_code == 200) 
    {
        std::cout << "backend is healthy" << std::endl;
        return 0;
    } 
    else 
    {
        std::cout << "backend unreachable or unhealthy" << std::endl;
        return 1;
    }
    
}