-- Database initialization script
-- This runs automatically when the PostgreSQL container starts

-- Create the main database (already created by POSTGRES_DB env var)
-- Just ensure proper encoding and settings

-- Set timezone to UTC for consistency
SET timezone = 'UTC';

-- Enable UUID extension for generating unique IDs
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create logs directory structure if needed
-- (Drizzle will handle table creation via migrations)