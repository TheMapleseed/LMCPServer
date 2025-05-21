/**
 * @file caicr_network.h
 * @brief Network Coordination Layer for Cursor AI Coordination Runtime
 * @version 1.0.0
 * @copyright Copyright (c) 2025, Enterprise Solutions Inc.
 *
 * Provides secure P2P communication between Cursor AI instances.
 */

#ifndef CAICR_NETWORK_H
#define CAICR_NETWORK_H

#include "caicr.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Network context for instance coordination
 */
typedef struct CAICRNetworkContext_t* CAICRNetworkContext;

/**
 * @brief Network configuration parameters
 */
typedef struct CAICRNetworkConfig {
    const char* instance_id;        ///< Instance identifier
    uint16_t port;                  ///< Network port
    bool encryption_enabled;        ///< Whether to enable encryption
} CAICRNetworkConfig;

/**
 * @brief Initialize network coordination context
 * 
 * @param config Network configuration
 * @param context Pointer to receive the context handle
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_network_initialize(const CAICRNetworkConfig* config,
                                    CAICRNetworkContext* context);

/**
 * @brief Distribute an operation to other instances
 * 
 * @param context Network context
 * @param operation Operation to distribute
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_network_distribute_operation(CAICRNetworkContext context,
                                             const CAICROperation* operation);

/**
 * @brief Synchronize state with other instances
 * 
 * @param context Network context
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_network_sync_state(CAICRNetworkContext context);

/**
 * @brief Get pending operations from other instances
 * 
 * @param context Network context
 * @param operations Pointer to receive linked list of operations
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_network_get_pending_operations(CAICRNetworkContext context,
                                               CAICROperation** operations);

/**
 * @brief Free operations retrieved from the network layer
 * 
 * @param context Network context
 * @param operations Operations to free
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_network_free_operations(CAICRNetworkContext context,
                                        CAICROperation* operations);

/**
 * @brief Shutdown the network context and free resources
 * 
 * @param context Network context
 * @return Status code indicating success or specific error
 */
CAICRStatus caicr_network_shutdown(CAICRNetworkContext context);

#ifdef __cplusplus
}
#endif

#endif /* CAICR_NETWORK_H */ 