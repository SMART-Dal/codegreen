#pragma once

#include <string>

namespace codegreen {

/// Get the type of IDE currently running
std::string get_ide_type();

/// Check if an IDE is currently running
bool is_ide_running();

} // namespace codegreen
