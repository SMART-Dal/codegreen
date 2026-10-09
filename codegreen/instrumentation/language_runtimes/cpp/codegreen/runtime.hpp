#pragma once

#include <string>
#include <sstream>

// Import C API (NEMB backend handles invocation tracking)
extern "C" {
    void nemb_mark_checkpoint(const char* name);
}

namespace CodeGreen {

/**
 * Mark a checkpoint in the energy measurement stream.
 *
 * Invocation tracking is handled automatically by the NEMB C++ backend.
 * Each call to the same checkpoint gets a unique invocation counter (#inv_N)
 * without any overhead in the language runtime.
 *
 * @param id Unique identifier for the checkpoint
 * @param name Human-readable name
 * @param type Type of checkpoint (enter, exit, etc.)
 */
inline void checkpoint(const std::string& id, const std::string& name, const std::string& type) {
    // Simple pass-through to NEMB backend
    // Format: "type:name:id" - invocation counter added by backend
    std::stringstream ss;
    ss << type << ":" << name << ":" << id;
    nemb_mark_checkpoint(ss.str().c_str());
}

/**
 * Function frame: enter on construction, exit on destruction. The destructor runs after the return value is
 * constructed and on every exit path (return, exception), so the frame owns the work inside return expressions
 * and exit never mis-pairs. The ids and name must outlive the frame (string literals).
 */
class Frame {
    const char* id_;
    const char* name_;
public:
    Frame(const char* id, const char* name) : id_(id), name_(name) { checkpoint(id_, name_, "enter"); }
    ~Frame() { checkpoint(id_, name_, "exit"); }
    Frame(const Frame&) = delete;
    Frame& operator=(const Frame&) = delete;
};

} // namespace CodeGreen
