# utils/security.py
"""
Security Utilities

This module provides security-related utility functions for the
Cursor AI coordination service.
"""

import os
import uuid
import hmac
import hashlib
import base64
import secrets
from typing import Optional, Tuple


def generate_secure_id(prefix: str = "caicr-") -> str:
    """
    Generate a secure identifier.
    
    Args:
        prefix: Prefix for the identifier
    
    Returns:
        str: Secure identifier
    """
    # Generate a UUID
    id_uuid = uuid.uuid4()
    
    # Convert to string and add prefix
    return f"{prefix}{id_uuid}"


def generate_hmac(
    message: bytes,
    key: bytes,
    algorithm: str = "sha256"
) -> bytes:
    """
    Generate an HMAC signature for a message.
    
    Args:
        message: Message to sign
        key: Signing key
        algorithm: Hash algorithm to use
    
    Returns:
        bytes: HMAC signature
    """
    h = hmac.new(key, message, getattr(hashlib, algorithm))
    return h.digest()


def verify_hmac(
    message: bytes,
    signature: bytes,
    key: bytes,
    algorithm: str = "sha256"
) -> bool:
    """
    Verify an HMAC signature for a message.
    
    Args:
        message: Message that was signed
        signature: Signature to verify
        key: Signing key
        algorithm: Hash algorithm used
    
    Returns:
        bool: True if the signature is valid, False otherwise
    """
    expected = generate_hmac(message, key, algorithm)
    return hmac.compare_digest(signature, expected)


def generate_keypair() -> Tuple[bytes, bytes]:
    """
    Generate a key pair for encryption and signing.
    
    Returns:
        Tuple[bytes, bytes]: (private_key, public_key)
    """
    # This is a placeholder - in a real implementation, this would use
    # a proper cryptographic library like PyNaCl or cryptography
    private_key = secrets.token_bytes(32)
    public_key = hashlib.sha256(private_key).digest()
    
    return private_key, public_key


def encrypt_message(
    message: bytes,
    public_key: bytes
) -> Tuple[bytes, bytes]:
    """
    Encrypt a message with a public key.
    
    Args:
        message: Message to encrypt
        public_key: Recipient's public key
    
    Returns:
        Tuple[bytes, bytes]: (encrypted_message, nonce)
    """
    # This is a placeholder - in a real implementation, this would use
    # a proper cryptographic library like PyNaCl or cryptography
    nonce = secrets.token_bytes(24)
    key = hashlib.sha256(public_key + nonce).digest()
    encrypted = bytes([a ^ b for a, b in zip(message, key * (len(message) // len(key) + 1))])
    
    return encrypted, nonce


def decrypt_message(
    encrypted_message: bytes,
    nonce: bytes,
    private_key: bytes
) -> bytes:
    """
    Decrypt a message with a private key.
    
    Args:
        encrypted_message: Encrypted message
        nonce: Nonce used for encryption
        private_key: Recipient's private key
    
    Returns:
        bytes: Decrypted message
    """
    # This is a placeholder - in a real implementation, this would use
    # a proper cryptographic library like PyNaCl or cryptography
    public_key = hashlib.sha256(private_key).digest()
    key = hashlib.sha256(public_key + nonce).digest()
    decrypted = bytes([a ^ b for a, b in zip(encrypted_message, key * (len(encrypted_message) // len(key) + 1))])
    
    return decrypted 