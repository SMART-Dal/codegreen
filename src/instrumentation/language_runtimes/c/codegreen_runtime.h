#ifndef CODEGREEN_RUNTIME_H
#define CODEGREEN_RUNTIME_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/*
 * CodeGreen Runtime API for C
 * Links against libcodegreen-nemb.so
 *
 * Invocation tracking is handled automatically by the NEMB C++ backend.
 */

/**
 * Initialize the energy measurement backend.
 * Returns 1 on success, 0 on failure.
 */
int nemb_initialize();

/**
 * Mark a checkpoint in the energy measurement stream.
 * @param name The name of the checkpoint (e.g. "function_entry:main")
 */
void nemb_mark_checkpoint(const char* name);

/**
 * Checkpoint macro - simple pass-through to NEMB backend.
 * Invocation counter (#inv_N) is added automatically by the backend.
 */
#define codegreen_checkpoint(id, name, type) \
    do { \
        char _cg_buffer[256]; \
        snprintf(_cg_buffer, sizeof(_cg_buffer), "%s:%s:%s", type, name, id); \
        nemb_mark_checkpoint(_cg_buffer); \
    } while(0)

#ifdef __cplusplus
}
#endif

#endif // CODEGREEN_RUNTIME_H

