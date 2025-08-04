import { db } from './index';
import { users } from './schema';
import { sql } from 'drizzle-orm';

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
  }
}

// Run seed if called directly
if (require.main === module) {
  seed()
    .then(() => process.exit(0))
    .catch(() => process.exit(1));
}

export { seed };