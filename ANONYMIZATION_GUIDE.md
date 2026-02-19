# Evaluator Anonymization Implementation Guide

## Overview
This system anonymizes evaluator IDs using one-way cryptographic hashing (HMAC-SHA256). Once anonymized, evaluator identities cannot be determined from the database.

## How It Works

### 1. Hashing Function
- Uses `hash_evaluator_id(evaluator_id, cycle_id)` to create a unique hash
- Same evaluator + same cycle = same hash (for uniqueness checks)
- Different cycles = different hashes (prevents cross-cycle correlation)
- One-way: Cannot reverse hash to get original ID

### 2. Database Changes
- `FeedbackEvaluation.evaluator_id` → `FeedbackEvaluation.evaluator_hash`
- `RandomizationLog.evaluator_id` → `RandomizationLog.evaluator_hash`
- Removed foreign key relationships to `employees` table
- Added anonymized metadata fields for diversity calculations

### 3. Metadata for Diversity
- Stores hashed department, role, and manager relationship
- Allows diversity calculations without revealing identity
- Each metadata value is hashed separately

## Migration Steps

### Step 1: Run Migration Script
```bash
python migrate_anonymize_evaluators.py
```

This will:
1. Add new `evaluator_hash` columns
2. Migrate existing data
3. Remove old `evaluator_id` columns
4. Add indexes for performance

### Step 2: Update Code References
All code that uses `evaluator_id` must be updated to use `evaluator_hash`:
- Query filters
- Assignment creation
- Results display

### Step 3: Test
- Verify users can still submit evaluations
- Verify results display correctly
- Verify no evaluator information is exposed

## Security Notes

1. **Salt Key**: Change `EVALUATOR_SALT` in `anonymization.py` to a strong random value in production
2. **No Recovery**: Once migrated, original evaluator IDs cannot be recovered
3. **Backup First**: Always backup database before migration
4. **Testing**: Test migration on a copy of production data first

## Files Modified

- `models.py`: Updated FeedbackEvaluation and RandomizationLog models
- `anonymization.py`: New utility module for hashing
- `app_360.py`: Updated to use hashed IDs
- `results_visibility.py`: Updated diversity calculations
- `results_routes.py`: Removed evaluator references
- `seed_data.py`: Updated to use hashed IDs
- `migrate_anonymize_evaluators.py`: Migration script

## Important Notes

- KPI evaluations still use evaluator_id (manager-to-subordinate, not anonymous)
- Only 360-degree feedback is anonymized
- Users can still see their own assignments (using hashed lookup)
- Results pages show "Anonymous feedback" instead of evaluator names
