cmake_minimum_required(VERSION 3.15)
project(sensor_client VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(nlohmann_json 3.2 REQUIRED)
find_package(OpenSSL REQUIRED)

include(FetchContent)

# cpr for HTTP
FetchContent_Declare(
    cpr
    GIT_REPOSITORY https://github.com/libcpr/cpr.git
    GIT_TAG 1.10.5
)
FetchContent_MakeAvailable(cpr)

# Paho MQTT C library
set(PAHO_WITH_SSL FALSE CACHE BOOL "" FORCE)
set(PAHO_BUILD_STATIC TRUE CACHE BOOL "" FORCE)
set(PAHO_BUILD_SHARED FALSE CACHE BOOL "" FORCE)
set(PAHO_ENABLE_TESTING FALSE CACHE BOOL "" FORCE)
FetchContent_Declare(
    paho-mqtt-c
    GIT_REPOSITORY https://github.com/eclipse/paho.mqtt.c.git
    GIT_TAG v1.3.13
)
FetchContent_MakeAvailable(paho-mqtt-c)

add_executable(sensor_client
    src/main.cpp
    src/backend_client.cpp
    src/mqtt_client.cpp
    src/hmac_signer.cpp
    lib/sensorproto/sensor_message.cpp
)

target_include_directories(sensor_client PRIVATE
    inc
    lib/sensorproto
    lib/strutil
    lib/bytebuf
    ${paho-mqtt-c_SOURCE_DIR}/src
)

target_link_libraries(sensor_client PRIVATE
    cpr::cpr
    nlohmann_json::nlohmann_json
    paho-mqtt3a-static
    OpenSSL::Crypto
)