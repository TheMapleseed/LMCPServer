/**
 * @file cursor_ai_client.c
 * @brief Sample Cursor AI Client Integration
 * @version 1.0.0
 * @copyright Copyright (c) 2025, Enterprise Solutions Inc.
 */

#include "caicr.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <uuid/uuid.h>

/**
 * @brief Operation callback function
 * 
 * @param operations Operations received from other instances
 * @param user_data User context data
 */
static void operation_callback(const CAICROperation* operations, void* user_data) {
    printf("Received operations from other instances:\n");
    
    const CAICROperation* current = operations;
    while (current != NULL) {
        printf("  - Operation ID: %lu\n", current->operation_id);
        printf("    Type: %d\n", current->type);
        printf("    File: %s\n", current->file_path);
        printf("    Line: %u, Column: %u\n", current->line_number, current->column_number);
        printf("    From Instance: %s\n", current->instance_id);
        printf("    Timestamp: %lu ns\n", current->timestamp_ns);
        printf("\n");
        
        current = current->next;
    }
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        printf("Usage: %s <project_path> <port>\n", argv[0]);
        return EXIT_FAILURE;
    }
    
    const char* project_path = argv[1];
    uint16_t port = (uint16_t)atoi(argv[2]);
    
    // Generate a unique instance ID
    uuid_t uuid;
    char instance_id[37];
    
    uuid_generate(uuid);
    uuid_unparse_lower(uuid, instance_id);
    
    // Create LLDB database path
    char db_path[1024];
    snprintf(db_path, sizeof(db_path), "%s/.caicr_history.db", project_path);
    
    // Configure the runtime
    CAICRConfig config = {
        .instance_id = instance_id,
        .project_root = project_path,
        .lldb_database_path = db_path,
        .coordination_port = port,
        .sync_interval_ms = 1000,
        .max_history_entries = 1000,
        .encryption_enabled = true
    };
    
    // Initialize the runtime
    CAICRInstance instance = NULL;
    CAICRStatus status = caicr_initialize(&config, &instance);
    
    if (status != CAICR_SUCCESS) {
        printf("Failed to initialize the runtime: %d\n", status);
        return EXIT_FAILURE;
    }
    
    printf("Cursor AI Coordination Runtime initialized:\n");
    printf("  - Instance ID: %s\n", instance_id);
    printf("  - Project: %s\n", project_path);
    printf("  - Port: %hu\n", port);
    
    // Register for operation notifications
    status = caicr_register_operation_callback(instance, operation_callback, NULL);
    
    if (status != CAICR_SUCCESS) {
        printf("Failed to register operation callback: %d\n", status);
        caicr_shutdown(instance);
        return EXIT_FAILURE;
    }
    
    // Main loop
    char command[256];
    printf("\nEnter 'q' to quit, 'u' to undo, 'r' to redo, or any other string to create a sample operation.\n");
    
    while (1) {
        printf("> ");
        if (fgets(command, sizeof(command), stdin) == NULL) {
            break;
        }
        
        // Remove newline
        size_t len = strlen(command);
        if (len > 0 && command[len - 1] == '\n') {
            command[len - 1] = '\0';
        }
        
        // Process command
        if (strcmp(command, "q") == 0) {
            break;
        } else if (strcmp(command, "u") == 0) {
            printf("Undoing last operation...\n");
            status = caicr_undo(instance);
            if (status != CAICR_SUCCESS) {
                printf("Failed to undo: %d\n", status);
            }
        } else if (strcmp(command, "r") == 0) {
            printf("Redoing last undone operation...\n");
            status = caicr_redo(instance);
            if (status != CAICR_SUCCESS) {
                printf("Failed to redo: %d\n", status);
            }
        } else {
            // Create a sample operation
            CAICROperation operation = {
                .type = CAICR_OP_INSERT,
                .file_path = strdup("sample.txt"),
                .line_number = 1,
                .column_number = 1,
                .content = strdup(command),
                .content_length = strlen(command),
                .timestamp_ns = 0, // Will be set by the runtime
                .instance_id = strdup(instance_id),
                .operation_id = 0, // Will be set by the runtime
                .next = NULL
            };
            
            printf("Submitting operation: %s\n", command);
            status = caicr_submit_operation(instance, &operation);
            
            if (status != CAICR_SUCCESS) {
                printf("Failed to submit operation: %d\n", status);
            }
            
            free(operation.file_path);
            free(operation.content);
            free(operation.instance_id);
        }
    }
    
    // Shutdown the runtime
    printf("Shutting down...\n");
    caicr_shutdown(instance);
    
    return EXIT_SUCCESS;
} 