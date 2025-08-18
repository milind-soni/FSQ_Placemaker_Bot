-- Setup script for PlacePilot PostgreSQL database
-- Run this as postgres superuser

-- Create user
CREATE USER placemaker WITH PASSWORD 'placemaker123';

-- Create database
CREATE DATABASE placemaker_db OWNER placemaker;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE placemaker_db TO placemaker;

-- Connect to the database and grant schema privileges
\c placemaker_db;
GRANT ALL ON SCHEMA public TO placemaker;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO placemaker;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO placemaker;

-- Grant default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO placemaker;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO placemaker; 