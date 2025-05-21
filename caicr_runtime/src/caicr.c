/**
 * @file caicr.c
 * @brief Cursor AI Coordination Runtime - Core Implementation
 * @version 1.0.0
 * @copyright Copyright (c) 2025, Enterprise Solutions Inc.
 */

#include "caicr.h"
#include "caicr_lldb.h"
#include "caicr_network.h"
#include <stdlib.h>
#include <string.h>
#include <time.h>

/**
 * @brief Runtime instance structure
 */
struct CAICRInstance_t {
    CAICRConfig config;                   ///< Configuration parameters
    CAICRLLDBContext lldb_context;        ///< LLDB database context
    CAICRNetworkContext network_context;  ///< Network communication context
    mtx_t mutex;                          ///< Instance mutex for thread safety
    atomic_bool is_running;               ///< Atomic flag indicating runtime state
    thrd_t sync_thread;                   ///< Synchronization thread
    CAICROperationCallback callback;      ///< User operation callback
    void* callback_user_data;             ///< User callback context
};

/**
 * @brief Synchronization thread function
 * 
 * @param arg Runtime instance
 * @return Thread result code
 */
static int caicr_sync_thread_func(void* arg) {
    CAICRInstance instance = (CAICRInstance)arg;
    struct timespec sleep_time;
    
    // Configure sleep time based on sync interval
    sleep_time.tv_sec = instance->config.sync_interval_ms / 1000;
    sleep_time.tv_nsec = (instance->config.sync_interval_ms % 1000) * 1000000;
    
    while (atomic_load(&instance->is_running)) {
        // Synchronize state with other instances
        caicr_network_sync_state(instance->network_context);
        
        // Process incoming operations
        CAICROperation* operations = NULL;
        if (caicr_network_get_pending_operations(instance->network_context, &operations) == CAICR_SUCCESS) {
            if (operations != NULL && instance->callback != NULL) {
                // Call the user callback with operations
                instance->callback(operations, instance->callback_user_data);
                
                // Store operations in the database
                mtx_lock(&instance->mutex);
                CAICROperation* current = operations;
                while (current != NULL) {
                    caicr_lldb_store_operation(instance->lldb_context, current);
                    current = current->next;
                }
                mtx_unlock(&instance->mutex);
                
                // Free the operations (owned by the network layer)
                caicr_network_free_operations(instance->network_context, operations);
            }
        }
        
        // Sleep until the next sync interval
        thrd_sleep(&sleep_time, NULL);
    }
    
    return 0;
}

CAICRStatus caicr_initialize(const CAICRConfig* config, CAICRInstance* instance) {
    if (config == NULL || instance == NULL) {
        return CAICR_ERROR_INVALID_PARAMETER;
    }
    
    // Allocate instance structure
    CAICRInstance new_instance = (CAICRInstance)calloc(1, sizeof(struct CAICRInstance_t));
    if (new_instance == NULL) {
        return CAICR_ERROR_OUT_OF_MEMORY;
    }
    
    // Copy configuration parameters
    new_instance->config.instance_id = strdup(config->instance_id);
    new_instance->config.project_root = strdup(config->project_root);
    new_instance->config.lldb_database_path = strdup(config->lldb_database_path);
    new_instance->config.coordination_port = config->coordination_port;
    new_instance->config.sync_interval_ms = config->sync_interval_ms;
    new_instance->config.max_history_entries = config->max_history_entries;
    new_instance->config.encryption_enabled = config->encryption_enabled;
    
    // Check for allocation failures
    if (new_instance->config.instance_id == NULL ||
        new_instance->config.project_root == NULL ||
        new_instance->config.lldb_database_path == NULL) {
        
        // Free allocated strings
        free((void*)new_instance->config.instance_id);
        free((void*)new_instance->config.project_root);
        free((void*)new_instance->config.lldb_database_path);
        free(new_instance);
        
        return CAICR_ERROR_OUT_OF_MEMORY;
    }
    
    // Initialize mutex
    if (mtx_init(&new_instance->mutex, mtx_plain) != thrd_success) {
        free((void*)new_instance->config.instance_id);
        free((void*)new_instance->config.project_root);
        free((void*)new_instance->config.lldb_database_path);
        free(new_instance);
        
        return CAICR_ERROR_UNKNOWN;
    }
    
    // Initialize LLDB context
    CAICRStatus status = caicr_lldb_initialize(config->lldb_database_path,
                                              config->max_history_entries,
                                              &new_instance->lldb_context);
    if (status != CAICR_SUCCESS) {
        mtx_destroy(&new_instance->mutex);
        free((void*)new_instance->config.instance_id);
        free((void*)new_instance->config.project_root);
        free((void*)new_instance->config.lldb_database_path);
        free(new_instance);
        
        return status;
    }
    
    // Initialize network context
    CAICRNetworkConfig network_config = {
        .instance_id = config->instance_id,
        .port = config->coordination_port,
        .encryption_enabled = config->encryption_enabled
    };
    
    status = caicr_network_initialize(&network_config, &new_instance->network_context);
    if (status != CAICR_SUCCESS) {
        caicr_lldb_shutdown(new_instance->lldb_context);
        mtx_destroy(&new_instance->mutex);
        free((void*)new_instance->config.instance_id);
        free((void*)new_instance->config.project_root);
        free((void*)new_instance->config.lldb_database_path);
        free(new_instance);
        
        return status;
    }
    
    // Set the running flag and start the synchronization thread
    atomic_store(&new_instance->is_running, true);
    
    if (thrd_create(&new_instance->sync_thread, caicr_sync_thread_func, new_instance) != thrd_success) {
        atomic_store(&new_instance->is_running, false);
        caicr_network_shutdown(new_instance->network_context);
        caicr_lldb_shutdown(new_instance->lldb_context);
        mtx_destroy(&new_instance->mutex);
        free((void*)new_instance->config.instance_id);
        free((void*)new_instance->config.project_root);
        free((void*)new_instance->config.lldb_database_path);
        free(new_instance);
        
        return CAICR_ERROR_UNKNOWN;
    }
    
    // Return the initialized instance
    *instance = new_instance;
    return CAICR_SUCCESS;
}

CAICRStatus caicr_register_operation_callback(CAICRInstance instance, 
                                             CAICROperationCallback callback,
                                             void* user_data) {
    if (instance == NULL) {
        return CAICR_ERROR_INVALID_PARAMETER;
    }
    
    mtx_lock(&instance->mutex);
    instance->callback = callback;
    instance->callback_user_data = user_data;
    mtx_unlock(&instance->mutex);
    
    return CAICR_SUCCESS;
}

CAICRStatus caicr_submit_operation(CAICRInstance instance, const CAICROperation* operation) {
    if (instance == NULL || operation == NULL) {
        return CAICR_ERROR_INVALID_PARAMETER;
    }
    
    CAICRStatus status;
    
    // Begin a transaction
    mtx_lock(&instance->mutex);
    status = caicr_lldb_begin_transaction(instance->lldb_context);
    if (status != CAICR_SUCCESS) {
        mtx_unlock(&instance->mutex);
        return status;
    }
    
    // Store the operation in LLDB
    status = caicr_lldb_store_operation(instance->lldb_context, operation);
    if (status != CAICR_SUCCESS) {
        caicr_lldb_rollback_transaction(instance->lldb_context);
        mtx_unlock(&instance->mutex);
        return status;
    }
    
    // Commit the transaction
    status = caicr_lldb_commit_transaction(instance->lldb_context);
    mtx_unlock(&instance->mutex);
    
    if (status != CAICR_SUCCESS) {
        return status;
    }
    
    // Distribute the operation to other instances
    return caicr_network_distribute_operation(instance->network_context, operation);
}

CAICRStatus caicr_undo(CAICRInstance instance) {
    if (instance == NULL) {
        return CAICR_ERROR_INVALID_PARAMETER;
    }
    
    CAICRStatus status;
    CAICROperation* last_operation = NULL;
    
    // Get the last operation
    mtx_lock(&instance->mutex);
    status = caicr_lldb_get_last_operation(instance->lldb_context, &last_operation);
    
    if (status != CAICR_SUCCESS || last_operation == NULL) {
        mtx_unlock(&instance->mutex);
        return (status != CAICR_SUCCESS) ? status : CAICR_ERROR_OPERATION_EXECUTION;
    }
    
    // Begin a transaction
    status = caicr_lldb_begin_transaction(instance->lldb_context);
    if (status != CAICR_SUCCESS) {
        caicr_free_operation(last_operation);
        mtx_unlock(&instance->mutex);
        return status;
    }
    
    // Mark the operation as undone
    status = caicr_lldb_mark_operation_undone(instance->lldb_context, last_operation->operation_id);
    
    if (status != CAICR_SUCCESS) {
        caicr_lldb_rollback_transaction(instance->lldb_context);
        caicr_free_operation(last_operation);
        mtx_unlock(&instance->mutex);
        return status;
    }
    
    // Create a reversal operation
    CAICROperation reverse_operation = {
        .type = (last_operation->type == CAICR_OP_INSERT) ? CAICR_OP_DELETE :
                (last_operation->type == CAICR_OP_DELETE) ? CAICR_OP_INSERT : CAICR_OP_REPLACE,
        .file_path = strdup(last_operation->file_path),
        .line_number = last_operation->line_number,
        .column_number = last_operation->column_number,
        .content = (last_operation->type == CAICR_OP_DELETE) ? strdup(last_operation->content) : NULL,
        .content_length = (last_operation->type == CAICR_OP_DELETE) ? last_operation->content_length : 0,
        .timestamp_ns = 0, // Will be set by the network layer
        .instance_id = strdup(instance->config.instance_id),
        .operation_id = 0, // Will be set by the network layer
        .next = NULL
    };
    
    // Complete the transaction
    status = caicr_lldb_commit_transaction(instance->lldb_context);
    mtx_unlock(&instance->mutex);
    
    if (status != CAICR_SUCCESS) {
        free(reverse_operation.file_path);
        free(reverse_operation.content);
        free(reverse_operation.instance_id);
        caicr_free_operation(last_operation);
        return status;
    }
    
    // Distribute the undo operation
    status = caicr_network_distribute_operation(instance->network_context, &reverse_operation);
    
    // Clean up
    free(reverse_operation.file_path);
    free(reverse_operation.content);
    free(reverse_operation.instance_id);
    caicr_free_operation(last_operation);
    
    return status;
}

CAICRStatus caicr_redo(CAICRInstance instance) {
    // Implementation similar to caicr_undo but for redo operations
    // ...
    return CAICR_SUCCESS; // Placeholder for brevity
}

void caicr_free_operation(CAICROperation* operation) {
    if (operation == NULL) {
        return;
    }
    
    free(operation->file_path);
    free(operation->content);
    free(operation->instance_id);
    free(operation);
}

CAICRStatus caicr_shutdown(CAICRInstance instance) {
    if (instance == NULL) {
        return CAICR_ERROR_INVALID_PARAMETER;
    }
    
    // Stop the synchronization thread
    atomic_store(&instance->is_running, false);
    thrd_join(instance->sync_thread, NULL);
    
    // Shutdown the network and LLDB contexts
    caicr_network_shutdown(instance->network_context);
    caicr_lldb_shutdown(instance->lldb_context);
    
    // Destroy the mutex
    mtx_destroy(&instance->mutex);
    
    // Free the configuration strings
    free((void*)instance->config.instance_id);
    free((void*)instance->config.project_root);
    free((void*)instance->config.lldb_database_path);
    
    // Free the instance
    free(instance);
    
    return CAICR_SUCCESS;
} 