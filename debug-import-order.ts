// Test 1: Config AFTER imports (like manual-gmail-test.ts)
import { config } from 'dotenv';
import { db } from '../src/lib/db';

config();

async function test1() {
  console.log('Test 1 - Config after imports:');
  try {
    await db.select().from({ users: {} as any }).limit(1);
    console.log('✅ Works');
  } catch (e) {
    console.log('❌ Failed:', e.message);
  }
}

test1();