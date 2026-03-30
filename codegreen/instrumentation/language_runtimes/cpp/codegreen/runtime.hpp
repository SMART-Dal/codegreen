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

} // namespace CodeGreen
