#!/usr/bin/env tsx
/**
 * Run All Integration Tests
 * 
 * Executes all integration tests in sequence and provides a summary
 */

import { spawn } from 'child_process';
import path from 'path';

interface TestResult {
  name: string;
  passed: boolean;
  duration: number;
  output: string;
}

const tests = [
  { name: 'Gmail OAuth', file: 'gmail-oauth.test.ts' },
  { name: 'Sync Pipeline', file: 'sync-pipeline.test.ts' },
  { name: 'Subscription CRUD', file: 'subscription-crud.test.ts' },
];

async function runTest(name: string, file: string): Promise<TestResult> {
  const startTime = Date.now();
  const testPath = path.join(__dirname, file);
  
  return new Promise((resolve) => {
    let output = '';
    
    const child = spawn('tsx', [testPath], {
      cwd: process.cwd(),
      env: { ...process.env },
    });
    
    child.stdout.on('data', (data) => {
      output += data.toString();
      process.stdout.write(data);
    });
    
    child.stderr.on('data', (data) => {
      output += data.toString();
      process.stderr.write(data);
    });
    
    child.on('close', (code) => {
      const duration = Date.now() - startTime;
      resolve({
        name,
        passed: code === 0,
        duration,
        output,
      });
    });
  });
}

async function main() {
  console.log('========================================');
  console.log('🧪 Running All Integration Tests');
  console.log('========================================\n');
  
  const results: TestResult[] = [];
  
  for (const test of tests) {
    console.log(`\n📋 Running: ${test.name}`);
    console.log('----------------------------------------\n');
    
    const result = await runTest(test.name, test.file);
    results.push(result);
    
    if (!result.passed) {
      console.log(`\n❌ ${test.name} failed\n`);
    }
  }
  
  // Print summary
  console.log('\n========================================');
  console.log('📊 Test Summary');
  console.log('========================================\n');
  
  const passed = results.filter(r => r.passed).length;
  const failed = results.filter(r => !r.passed).length;
  const totalDuration = results.reduce((sum, r) => sum + r.duration, 0);
  
  results.forEach(result => {
    const status = result.passed ? '✅' : '❌';
    const time = (result.duration / 1000).toFixed(2);
    console.log(`${status} ${result.name.padEnd(20)} (${time}s)`);
  });
  
  console.log('\n----------------------------------------');
  console.log(`Total: ${results.length} tests`);
  console.log(`Passed: ${passed} ✅`);
  console.log(`Failed: ${failed} ❌`);
  console.log(`Duration: ${(totalDuration / 1000).toFixed(2)}s`);
  console.log('========================================\n');
  
  // Exit with appropriate code
  process.exit(failed > 0 ? 1 : 0);
}

// Run tests
main().catch(console.error);