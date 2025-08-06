require('dotenv').config();
const { Pool } = require('pg');

console.log('Testing minimal database connection...');
console.log('Password from env:', JSON.stringify(process.env.POSTGRES_PASSWORD));

const pool = new Pool({
  user: 'postgres',
  password: process.env.POSTGRES_PASSWORD,
  host: 'localhost',
  port: 5432,
  database: 'subscriptions'
});

pool.query('SELECT 1 as test')
  .then(result => {
    console.log('✅ Minimal connection works:', result.rows[0]);
    pool.end();
  })
  .catch(error => {
    console.error('❌ Minimal connection failed:', error.message);
    pool.end();
  });