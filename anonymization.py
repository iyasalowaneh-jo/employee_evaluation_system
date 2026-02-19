"""
Anonymization utilities for evaluator IDs
Uses one-way hashing to ensure evaluator identity cannot be determined
"""
import hashlib
import hmac
import os

# Secret key for hashing - in production, use environment variable
# You can set EVALUATOR_SALT environment variable for production
_salt_env = os.getenv('EVALUATOR_SALT')
if _salt_env:
    EVALUATOR_SALT = _salt_env.encode() if isinstance(_salt_env, str) else _salt_env
else:
    EVALUATOR_SALT = b'evaluator_anonymization_salt_2024'  # Change this in production!

def hash_evaluator_id(evaluator_id, cycle_id):
    """
    Create a one-way hash of evaluator_id + cycle_id
    This ensures:
    - Same evaluator in same cycle = same hash (for uniqueness)
    - Cannot reverse to get original evaluator_id
    - Different cycles = different hashes (prevents cross-cycle correlation)
    
    Args:
        evaluator_id: The actual employee ID
        cycle_id: The evaluation cycle ID
        
    Returns:
        str: Hexadecimal hash (64 characters for SHA-256)
    """
    # Combine evaluator_id and cycle_id with salt
    message = f"{evaluator_id}_{cycle_id}".encode('utf-8')
    
    # Use HMAC for additional security
    hash_obj = hmac.new(EVALUATOR_SALT, message, hashlib.sha256)
    return hash_obj.hexdigest()

def hash_evaluator_metadata(evaluator_id, cycle_id, metadata_type, value):
    """
    Hash evaluator metadata (department, role, etc.) for diversity calculations
    This allows us to calculate diversity without revealing identity
    
    Args:
        evaluator_id: The actual employee ID
        cycle_id: The evaluation cycle ID
        metadata_type: Type of metadata ('department', 'role', 'is_manager')
        value: The metadata value
        
    Returns:
        str: Hexadecimal hash
    """
    message = f"{evaluator_id}_{cycle_id}_{metadata_type}_{value}".encode('utf-8')
    hash_obj = hmac.new(EVALUATOR_SALT, message, hashlib.sha256)
    return hash_obj.hexdigest()

def get_metadata_hash_groups(hashed_metadata_list):
    """
    Get distinct metadata groups from hashed metadata
    This allows diversity calculation without revealing identity
    
    Args:
        hashed_metadata_list: List of hashed metadata values
        
    Returns:
        set: Distinct metadata groups
    """
    return set(hashed_metadata_list)
