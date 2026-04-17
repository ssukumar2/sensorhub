#pragma once

#include <string>
#include <cstdint>

/// Provides HMAC-SHA256 signing for request payloads.
///
/// Usage:
///   HmacSigner signer(api_key);
///   auto sig = signer.sign(payload);
///   // send sig in x-signature header
///
/// The server can verify by recomputing HMAC-SHA256(api_key, payload)
/// and comparing with the received signature.
class HmacSigner 
{
public:
    explicit HmacSigner(std::string secret_key);

    /// Compute HMAC-SHA256 of the given message using the stored key.
    /// Returns hex-encoded string (64 chars).
    std::string sign(const std::string& message) const;

    /// Compute HMAC-SHA256 and compare against expected signature.
    /// Uses constant-time comparison to prevent timing attacks.
    bool verify(const std::string& message, const std::string& expected_signature) const;

private:
    std::string secret_key_;

    /// Constant-time string comparison to prevent timing side-channels.
    static bool constant_time_compare(const std::string& a, const std::string& b);
};