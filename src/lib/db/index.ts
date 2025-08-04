import { drizzle } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';
import * as schema from './schema';

// Create connection pool
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 10, // Maximum 10 connections for single-user MVP
});

// Create Drizzle database instance
export const db = drizzle(pool, { schema });

// Export types and schema
export * from './schema';
export type Database = typeof db;