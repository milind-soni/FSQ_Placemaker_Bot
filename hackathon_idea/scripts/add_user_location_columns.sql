-- Migration: Add latitude and longitude columns to users table
-- This enables persistent location storage for users

-- Add latitude column
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS latitude FLOAT;

-- Add longitude column  
ALTER TABLE users
ADD COLUMN IF NOT EXISTS longitude FLOAT;

-- Add comments for documentation
COMMENT ON COLUMN users.latitude IS 'User saved latitude for persistent location functionality';
COMMENT ON COLUMN users.longitude IS 'User saved longitude for persistent location functionality';

-- Optional: Create index for location-based queries (if needed in the future)
-- CREATE INDEX IF NOT EXISTS idx_users_location ON users (latitude, longitude);

-- Verify the migration
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'users' 
  AND column_name IN ('latitude', 'longitude'); 