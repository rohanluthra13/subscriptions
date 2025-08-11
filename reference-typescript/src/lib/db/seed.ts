import { drizzle } from 'drizzle-orm/node-postgres';
import { Pool } from 'pg';
import { users } from './schema';
import { sql } from 'drizzle-orm';

// Direct database connection for seeding (bypasses env validation)
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

const db = drizzle(pool, { schema: { users } });

async function seed() {
  console.log('🌱 Seeding database...');
  
  try {
    // Insert default user for MVP
    await db.insert(users)
      .values({
        id: '1',
        email: 'default@localhost',
        name: 'Default User',
      })
      .onConflictDoNothing();
      
    console.log('✅ Default user created');
    console.log('🌱 Database seeded successfully');
  } catch (error) {
    console.error('❌ Error seeding database:', error);
    throw error;
  } finally {
    await pool.end();
  }
}

// Run seed if called directly
if (require.main === module) {
  seed()
    .then(() => process.exit(0))
    .catch(() => process.exit(1));
}

export { seed };