#!/usr/bin/env node

/**
 * Database reset script for development
 * Drops all tables and recreates them with fresh migrations
 */

const { execSync } = require('child_process');
const path = require('path');

function runCommand(command, description) {
  console.log(`🔄 ${description}...`);
  try {
    execSync(command, { 
      stdio: 'inherit', 
      cwd: path.resolve(__dirname, '..'),
      env: { ...process.env }
    });
    console.log(`✅ ${description} completed`);
  } catch (error) {
    console.error(`❌ ${description} failed:`, error.message);
    process.exit(1);
  }
}

async function resetDatabase() {
  console.log('🗃️  Resetting database for development...');
  
  // Drop all tables by pushing empty schema
  runCommand('npx drizzle-kit drop', 'Dropping existing tables');
  
  // Push new schema
  runCommand('npx drizzle-kit push', 'Creating fresh tables');
  
  // Run seed
  runCommand('npm run db:seed', 'Seeding database');
  
  console.log('🎉 Database reset complete!');
}

// Run if called directly
if (require.main === module) {
  resetDatabase().catch(console.error);
}

module.exports = { resetDatabase };