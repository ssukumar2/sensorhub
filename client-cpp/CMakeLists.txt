cmake_minimum_required(VERSION 3.15)
project(sensor_client VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Dependencies
# nlohmann/json installed via apt
find_package(nlohmann_json 3.2 REQUIRED)

# cpr fetched from GitHub
include(FetchContent)
FetchContent_Declare(
    cpr
    GIT_REPOSITORY https://github.com/libcpr/cpr.git
    GIT_TAG 1.10.5
)
FetchContent_MakeAvailable(cpr)

# Our executable
add_executable(sensor_client 
src/main.cpp
src/backend_client.cpp
)

target_include_directories(sensor_client PRIVATE inc)

target_link_libraries(sensor_client PRIVATE cpr::cpr nlohmann_json::nlohmann_json)