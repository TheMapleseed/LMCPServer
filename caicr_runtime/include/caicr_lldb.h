/**
 * @file caicr_lldb.h
 * @brief LLDB Integration Layer for Cursor AI Coordination Runtime
 * @version 1.0.0
 * @copyright Copyright (c) 2025, Enterprise Solutions Inc.
 *
 * Provides persistence and history tracking functionality using LLDB.
 */

#ifndef CAICR_LLDB_H
#define CAICR_LLDB_H

#include "caicr.h"
#include <lldb/API/LLDB.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief LLDB database context
 */
typedef struct CAICRLLDBContext_t* CAICRLLDBContext;

/**
 * @brief Initialize LLDB database context
 * 
 * @param db_path Path to the database file
 * @param max_history Maximum history entries to maintain
 * @param context Pointer to receive the context handle
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_lldb_initialize(const char* db_path, 
                                 size_t max_history,
                                 CAICRLLDBContext* context);

/**
 * @brief Begin a transaction in the LLDB database
 * 
 * @param context LLDB context
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_lldb_begin_transaction(CAICRLLDBContext context);

/**
 * @brief Commit a transaction in the LLDB database
 * 
 * @param context LLDB context
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_lldb_commit_transaction(CAICRLLDBContext context);

/**
 * @brief Rollback a transaction in the LLDB database
 * 
 * @param context LLDB context
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_lldb_rollback_transaction(CAICRLLDBContext context);

/**
 * @brief Store an operation in the LLDB database
 * 
 * @param context LLDB context
 * @param operation Operation to store
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_lldb_store_operation(CAICRLLDBContext context,
                                      const CAICROperation* operation);

/**
 * @brief Retrieve last operation from the LLDB database
 * 
 * @param context LLDB context
 * @param operation Pointer to receive the operation
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_lldb_get_last_operation(CAICRLLDBContext context,
                                         CAICROperation** operation);

/**
 * @brief Retrieve operation history from the LLDB database
 * 
 * @param context LLDB context
 * @param limit Maximum number of operations to retrieve
 * @param operations Pointer to receive linked list of operations
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_lldb_get_operation_history(CAICRLLDBContext context,
                                           size_t limit,
                                           CAICROperation** operations);

/**
 * @brief Mark an operation as undone in the database
 * 
 * @param context LLDB context
 * @param operation_id ID of the operation to mark
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_lldb_mark_operation_undone(CAICRLLDBContext context,
                                            uint64_t operation_id);

/**
 * @brief Mark an operation as redone in the database
 * 
 * @param context LLDB context
 * @param operation_id ID of the operation to mark
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_lldb_mark_operation_redone(CAICRLLDBContext context,
                                           uint64_t operation_id);

/**
 * @brief Shutdown the LLDB context and free resources
 * 
 * @param context LLDB context
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_lldb_shutdown(CAICRLLDBContext context);

#ifdef __cplusplus
}
#endif

#endif /* CAICR_LLDB_H */ 