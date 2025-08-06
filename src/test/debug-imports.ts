import { config } from 'dotenv';

console.log('Password before config():', JSON.stringify(process.env.POSTGRES_PASSWORD));
config();
console.log('Password after config():', JSON.stringify(process.env.POSTGRES_PASSWORD));

console.log('\nTesting import order like manual-gmail-test.ts...');

// Import db first (this triggers the connection)
import { db } from '../lib/db';
console.log('Password after db import:', JSON.stringify(process.env.POSTGRES_PASSWORD));

// Test connection
async function test() {
  try {
    console.log('\nTrying db query...');
    // Simple query that doesn't need schema
    const result = await db.execute('SELECT 1 as test');
    console.log('✅ Database connection works!');
  } catch (error) {
    console.log('❌ Database connection failed:', error.message);
    console.log('   Password at error time:', JSON.stringify(process.env.POSTGRES_PASSWORD));
  }
}

test();