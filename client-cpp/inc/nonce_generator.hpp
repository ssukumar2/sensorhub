#pragma once

#include <string>
#include <chrono>
#include <random>
#include <sstream>
#include <iomanip>

/// Generates unique nonces and timestamps for replay protection.
///
/// Each request includes:
///   - A timestamp (unix epoch seconds)
///   - A random nonce (hex string)
///
/// The server rejects requests with:
///   - Timestamp older than MAX_AGE_SECONDS
///   - Duplicate nonce within the time window
class NonceGenerator 
{
public:
    /// Get current unix timestamp as string.
    static std::string timestamp() 
    {
        auto now = std::chrono::system_clock::now();
        auto epoch = std::chrono::duration_cast<std::chrono::seconds>(
            now.time_since_epoch()
        ).count();
        return std::to_string(epoch);
    }

    /// Generate a random 16-byte hex nonce (32 hex chars).
    static std::string generate_nonce() 
    {
        std::random_device rd;
        std::mt19937_64 gen(rd());
        std::uniform_int_distribution<uint64_t> dist;

        uint64_t part1 = dist(gen);
        uint64_t part2 = dist(gen);

        std::ostringstream hex;
        hex << std::hex << std::setfill('0');
        hex << std::setw(16) << part1;
        hex << std::setw(16) << part2;
        return hex.str();
    }
};