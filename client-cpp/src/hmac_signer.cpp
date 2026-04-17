#include "hmac_signer.hpp"

#include <openssl/hmac.h>
#include <openssl/evp.h>

#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <utility>
#include <cstring>

HmacSigner::HmacSigner(std::string secret_key) : secret_key_(std::move(secret_key)) 
{
    if (secret_key_.empty()) 
    {
        throw std::invalid_argument("HMAC secret key must not be empty");
    }
}

std::string HmacSigner::sign(const std::string& message) const 
{
    unsigned char result[EVP_MAX_MD_SIZE];
    unsigned int result_len = 0;

    unsigned char* hmac = HMAC(
        EVP_sha256(),
        secret_key_.data(),
        static_cast<int>(secret_key_.size()),
        reinterpret_cast<const unsigned char*>(message.data()),
        message.size(),
        result,
        &result_len
    );

    if (hmac == nullptr) 
    {
        throw std::runtime_error("HMAC computation failed");
    }

    // Convert to hex string
    std::ostringstream hex;
    hex << std::hex << std::setfill('0');
    for (unsigned int i = 0; i < result_len; ++i) 
    {
        hex << std::setw(2) << static_cast<int>(result[i]);
    }

    return hex.str();
}

bool HmacSigner::verify(const std::string& message, const std::string& expected_signature) const 
{
    std::string computed = sign(message);
    return constant_time_compare(computed, expected_signature);
}

bool HmacSigner::constant_time_compare(const std::string& a, const std::string& b) 
{
    if (a.size() != b.size()) 
    {
        return false;
    }
    volatile unsigned char diff = 0;
    
    for (size_t i = 0; i < a.size(); ++i) 
    {
        diff |= static_cast<unsigned char>(a[i]) ^ static_cast<unsigned char>(b[i]);
    }

    return diff == 0;
}