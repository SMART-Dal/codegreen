#include "../../../include/nemb/utils/non_blocking_file_reader.hpp"

#include <fcntl.h>
#include <unistd.h>
#include <sys/select.h>
#include <errno.h>
#include <cstring>
#include <iostream>

namespace codegreen::nemb::utils {

NonBlockingFileReader::NonBlockingFileReader(const std::string& path) 
    : file_path_(path) {
}

NonBlockingFileReader::~NonBlockingFileReader() {
    close_file();
}

NonBlockingFileReader::NonBlockingFileReader(NonBlockingFileReader&& other) noexcept
    : fd_(other.fd_), file_path_(std::move(other.file_path_)) {
    other.fd_ = -1;
}

NonBlockingFileReader& NonBlockingFileReader::operator=(NonBlockingFileReader&& other) noexcept {
    if (this != &other) {
        close_file();
        fd_ = other.fd_;
        file_path_ = std::move(other.file_path_);
        other.fd_ = -1;
    }
    return *this;
}

bool NonBlockingFileReader::open_file() {
    close_file();
    
    // Open file in non-blocking mode
    fd_ = open(file_path_.c_str(), O_RDONLY | O_NONBLOCK);
    if (fd_ == -1) {
        // Don't log errors here - let the caller handle it
        return false;
    }
    
    return true;
}

void NonBlockingFileReader::close_file() {
    if (fd_ != -1) {
        close(fd_);
        fd_ = -1;
    }
}

bool NonBlockingFileReader::read_uint64_with_timeout(uint64_t& value, std::chrono::milliseconds timeout) {
    if (fd_ == -1 && !open_file()) {
        return false;
    }
    
    // Reset file position to beginning
    if (lseek(fd_, 0, SEEK_SET) == -1) {
        return false;
    }
    
    // Use select() for timeout-based reading
    fd_set read_fds;
    FD_ZERO(&read_fds);
    FD_SET(fd_, &read_fds);
    
    struct timeval tv;
    tv.tv_sec = timeout.count() / 1000;
    tv.tv_usec = (timeout.count() % 1000) * 1000;
    
    int select_result = select(fd_ + 1, &read_fds, nullptr, nullptr, &tv);
    
    if (select_result == -1) {
        // Select error
        return false;
    } else if (select_result == 0) {
        // Timeout occurred
        return false;
    }
    
    // File is ready for reading
    char buffer[64];
    ssize_t bytes_read = read(fd_, buffer, sizeof(buffer) - 1);
    
    if (bytes_read <= 0) {
        return false;
    }
    
    buffer[bytes_read] = '\0';
    
    // Parse the value - handle both newline and no-newline cases
    char* endptr;
    value = strtoull(buffer, &endptr, 10);
    
    if (endptr == buffer) {
        // No digits found
        return false;
    }
    
    // Accept values ending with newline, whitespace, or end of string
    while (*endptr == ' ' || *endptr == '\t' || *endptr == '\n' || *endptr == '\r') {
        endptr++;
    }
    
    if (*endptr != '\0') {
        // Extra characters after number
        return false;
    }
    
    return true;
}

} // namespace codegreen::nemb::utils