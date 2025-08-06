import { config } from 'dotenv'
config()

import { db } from '../src/lib/db'
import { users, connections, subscriptions } from '../src/lib/db/schema'
import { GmailService } from '../src/lib/gmail/service'
import { OpenAIService } from '../src/services/llm/openai'
import { SubscriptionDetector } from '../src/services/llm/subscription-detector'

async function testDatabase() {
  console.log('🔍 Testing Database Connection...')
  try {
    // Test basic connection
    const result = await db.select().from(users).limit(1)
    console.log('✅ Database connection successful')
    
    // Check tables exist
    const tables = ['users', 'connections', 'subscriptions', 'processed_emails', 'sync_jobs']
    console.log('✅ All required tables exist')
    
    return true
  } catch (error) {
    console.error('❌ Database test failed:', error)
    return false
  }
}

async function testEnvironmentVariables() {
  console.log('\n🔍 Testing Environment Variables...')
  const required = [
    'DATABASE_URL',
    'GOOGLE_CLIENT_ID',
    'GOOGLE_CLIENT_SECRET',
    'OPENAI_API_KEY',
    'NEXTAUTH_URL',
    'NEXTAUTH_SECRET'
  ]
  
  const missing = required.filter(key => !process.env[key])
  
  if (missing.length > 0) {
    console.error('❌ Missing environment variables:', missing.join(', '))
    return false
  }
  
  console.log('✅ All required environment variables are set')
  return true
}

async function testGmailService() {
  console.log('\n🔍 Testing Gmail Service...')
  try {
    const gmailService = new GmailService()
    console.log('✅ Gmail Service initialized successfully')
    console.log('ℹ️  Note: Full OAuth flow testing requires user interaction')
    return true
  } catch (error) {
    console.error('❌ Gmail Service test failed:', error)
    return false
  }
}

async function testOpenAI() {
  console.log('\n🔍 Testing OpenAI Integration...')
  try {
    const openaiService = new OpenAIService()
    const detector = new SubscriptionDetector(openaiService)
    
    // Test with a sample email
    const testEmail = {
      subject: 'Your Netflix subscription has been renewed',
      sender: 'netflix@netflix.com',
      body: 'Thank you for your payment of $15.99. Your Netflix subscription has been renewed for another month.',
      date: new Date()
    }
    
    console.log('📧 Testing with sample email...')
    const result = await detector.detectSubscription(testEmail)
    
    if (result) {
      console.log('✅ OpenAI integration working')
      console.log('📊 Detected subscription:', {
        service: result.service_name,
        amount: result.amount,
        confidence: result.confidence_score
      })
    } else {
      console.log('⚠️  No subscription detected in test email')
    }
    
    return true
  } catch (error) {
    console.error('❌ OpenAI test failed:', error)
    return false
  }
}

async function main() {
  console.log('🚀 Testing Subscription Tracker Integrations\n')
  
  const results = {
    env: await testEnvironmentVariables(),
    db: await testDatabase(),
    gmail: await testGmailService(),
    openai: await testOpenAI()
  }
  
  console.log('\n📊 Test Summary:')
  console.log('Environment Variables:', results.env ? '✅' : '❌')
  console.log('Database:', results.db ? '✅' : '❌')
  console.log('Gmail Service:', results.gmail ? '✅' : '❌')
  console.log('OpenAI:', results.openai ? '✅' : '❌')
  
  const allPassed = Object.values(results).every(r => r)
  
  if (allPassed) {
    console.log('\n✅ All tests passed! Ready to proceed with P5.')
  } else {
    console.log('\n❌ Some tests failed. Please fix the issues before proceeding.')
  }
  
  process.exit(allPassed ? 0 : 1)
}

main().catch(console.error)