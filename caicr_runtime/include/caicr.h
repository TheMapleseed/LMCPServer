/**
 * @file caicr.h
 * @brief Cursor AI Coordination Runtime - Core Header
 * @version 1.0.0
 * @copyright Copyright (c) 2025, Enterprise Solutions Inc.
 *
 * Thread-safe, memory-safe runtime for Cursor AI coordination with
 * deterministic state management capabilities.
 */

#ifndef CAICR_H
#define CAICR_H

#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <threads.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Runtime instance configuration parameters
 */
typedef struct CAICRConfig {
    const char* instance_id;           ///< Unique identifier for this instance
    const char* project_root;          ///< Path to project root directory
    const char* lldb_database_path;    ///< Path to LLDB database file
    uint16_t coordination_port;        ///< Network port for instance coordination
    uint32_t sync_interval_ms;         ///< State synchronization interval in milliseconds
    size_t max_history_entries;        ///< Maximum number of history entries to maintain
    bool encryption_enabled;           ///< Whether to enable E2E encryption for coordination
} CAICRConfig;

/**
 * @brief Operation type for change tracking
 */
typedef enum CAICROperationType {
    CAICR_OP_INSERT,      ///< Content insertion
    CAICR_OP_DELETE,      ///< Content deletion
    CAICR_OP_REPLACE,     ///< Content replacement
    CAICR_OP_META_CHANGE, ///< Metadata modification
    CAICR_OP_RESOURCE     ///< Resource modification
} CAICROperationType;

/**
 * @brief Detailed change operation description
 */
typedef struct CAICROperation {
    CAICROperationType type;      ///< Operation type
    char* file_path;              ///< Relative path to affected file
    uint32_t line_number;         ///< Affected line number
    uint32_t column_number;       ///< Affected column number
    char* content;                ///< Operation content
    size_t content_length;        ///< Content length in bytes
    uint64_t timestamp_ns;        ///< Operation timestamp (nanoseconds since epoch)
    char* instance_id;            ///< ID of the initiating instance
    uint64_t operation_id;        ///< Unique operation identifier
    struct CAICROperation* next;  ///< Next operation in sequence (for batching)
} CAICROperation;

/**
 * @brief Runtime instance opaque handle
 */
typedef struct CAICRInstance_t* CAICRInstance;

/**
 * @brief Status codes for runtime operations
 */
typedef enum CAICRStatus {
    CAICR_SUCCESS = 0,
    CAICR_ERROR_INVALID_PARAMETER,
    CAICR_ERROR_OUT_OF_MEMORY,
    CAICR_ERROR_LLDB_INITIALIZATION,
    CAICR_ERROR_LLDB_QUERY,
    CAICR_ERROR_NETWORK_INITIALIZATION,
    CAICR_ERROR_INSTANCE_DISCOVERY,
    CAICR_ERROR_OPERATION_EXECUTION,
    CAICR_ERROR_PERSISTENCE,
    CAICR_ERROR_UNKNOWN
} CAICRStatus;

/**
 * @brief Callback for operation notifications
 * 
 * @param operations Linked list of operations (owned by the runtime)
 * @param user_data User-provided context data
 */
typedef void (*CAICROperationCallback)(const CAICROperation* operations, void* user_data);

/**
 * @brief Initialize a new runtime instance
 * 
 * Thread-safe function that initializes the CAICR runtime with the provided
 * configuration. Establishes LLDB connection and prepares the coordination
 * mechanism.
 * 
 * @param config Configuration parameters
 * @param instance Pointer to receive the instance handle
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_initialize(const CAICRConfig* config, CAICRInstance* instance);

/**
 * @brief Register for operation notifications
 * 
 * @param instance Runtime instance
 * @param callback Function to be called when operations are received
 * @param user_data User context passed to callback
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_register_operation_callback(CAICRInstance instance, 
                                             CAICROperationCallback callback,
                                             void* user_data);

/**
 * @brief Submit a new operation for execution and distribution
 * 
 * @param instance Runtime instance
 * @param operation Operation to execute and distribute
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_submit_operation(CAICRInstance instance, 
                                  const CAICROperation* operation);

/**
 * @brief Undo the last operation
 * 
 * @param instance Runtime instance
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_undo(CAICRInstance instance);

/**
 * @brief Redo the last undone operation
 * 
 * @param instance Runtime instance
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_redo(CAICRInstance instance);

/**
 * @brief Free resources associated with an operation
 * 
 * @param operation Operation to free
 */
void caicr_free_operation(CAICROperation* operation);

/**
 * @brief Shutdown the runtime instance and free resources
 * 
 * @param instance Runtime instance
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_shutdown(CAICRInstance instance);

#ifdef __cplusplus
}
#endif

#endif /* CAICR_H */ 