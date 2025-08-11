#!/usr/bin/env node

/**
 * Database migration script
 * Runs pending migrations in production/staging environments
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

async function runMigrations() {
  console.log('🗃️  Running database migrations...');
  
  // Ensure migrations are generated
  runCommand('npm run db:generate', 'Generating migrations');
  
  // Run migrations
  runCommand('npm run db:migrate', 'Applying migrations');
  
  console.log('🎉 Migrations complete!');
}

// Run if called directly
if (require.main === module) {
  runMigrations().catch(console.error);
}

module.exports = { runMigrations };