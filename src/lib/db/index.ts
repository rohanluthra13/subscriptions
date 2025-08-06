import { drizzle } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';
import * as schema from './schema';

// Lazy connection pool creation
let pool: Pool | null = null;
let dbInstance: ReturnType<typeof drizzle> | null = null;

function getDb() {
  if (!dbInstance) {
    pool = new Pool({
      user: 'postgres',
      password: process.env.POSTGRES_PASSWORD,
      host: 'localhost',
      port: 5432,
      database: 'subscriptions',
      max: 10, // Maximum 10 connections for single-user MVP
    });
    dbInstance = drizzle(pool, { schema });
  }
  return dbInstance;
}

// Export the lazy-loaded db instance
export const db = new Proxy({} as ReturnType<typeof drizzle>, {
  get(target, prop) {
    return getDb()[prop as keyof ReturnType<typeof drizzle>];
  }
});

// Export types and schema
export * from './schema';
export type Database = typeof db;