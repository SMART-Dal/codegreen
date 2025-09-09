#pragma once

#include <string>
#include <chrono>
#include <cstdint>

namespace codegreen::nemb::utils {

/**
 * Non-blocking file reader for energy measurement files
 * Prevents hanging on RAPL and other hardware interface files
 */
class NonBlockingFileReader {
private:
    int fd_ = -1;
    std::string file_path_;
    
public:
    explicit NonBlockingFileReader(const std::string& path);
    ~NonBlockingFileReader();
    
    // Disable copy constructor and assignment
    NonBlockingFileReader(const NonBlockingFileReader&) = delete;
    NonBlockingFileReader& operator=(const NonBlockingFileReader&) = delete;
    
    // Allow move semantics
    NonBlockingFileReader(NonBlockingFileReader&& other) noexcept;
    NonBlockingFileReader& operator=(NonBlockingFileReader&& other) noexcept;
    
    /**
     * Open the file in non-blocking mode
     * @return true if successful, false otherwise
     */
    bool open_file();
    
    /**
     * Close the file descriptor
     */
    void close_file();
    
    /**
     * Read a uint64 value with timeout protection
     * @param value Output value
     * @param timeout Maximum time to wait
     * @return true if successful, false on timeout or error
     */
    bool read_uint64_with_timeout(uint64_t& value, std::chrono::milliseconds timeout);
    
    /**
     * Check if the file is currently open
     * @return true if file descriptor is valid
     */
    bool is_open() const { return fd_ != -1; }
    
    /**
     * Get the file path
     * @return file path string
     */
    const std::string& get_path() const { return file_path_; }
};

} // namespace codegreen::nemb::utils