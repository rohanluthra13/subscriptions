import { EmailData } from './types';

export const SUBSCRIPTION_DETECTION_SYSTEM_PROMPT = `You are an expert at analyzing emails to detect subscription services. You focus on identifying recurring payments, memberships, and regular billing cycles. You are conservative and only mark something as a subscription when you have high confidence.`;

export const FEW_SHOT_EXAMPLES = [
  {
    input: `From: billing@netflix.com
Subject: Your Netflix payment was processed
Body: Hi John, Your monthly Netflix subscription of $15.99 has been charged to your card ending in 1234. Your next billing date is March 15, 2024. Thank you for being a Netflix member!`,
    output: {
      is_subscription: true,
      confidence_score: 0.95,
      vendor_name: "Netflix",
      vendor_email: "billing@netflix.com",
      amount: 15.99,
      currency: "USD",
      billing_cycle: "monthly",
      next_billing_date: "2024-03-15",
      reasoning: "Clear subscription billing email with amount, cycle, and next billing date"
    }
  },
  {
    input: `From: no-reply@amazon.com
Subject: Your order has shipped
Body: Your order #123-456 containing "iPhone Case" has shipped and will arrive by Tuesday. Track your package at...`,
    output: {
      is_subscription: false,
      confidence_score: 0.9,
      reasoning: "One-time purchase order shipment, not a recurring subscription"
    }
  },
  {
    input: `From: team@github.com
Subject: Your GitHub Pro plan renewed
Body: Thanks for your continued support! Your GitHub Pro plan has been renewed for another year at $84.00. Your subscription will automatically renew on January 5, 2025.`,
    output: {
      is_subscription: true,
      confidence_score: 0.98,
      vendor_name: "GitHub",
      vendor_email: "team@github.com",
      amount: 84.00,
      currency: "USD",
      billing_cycle: "yearly",
      next_billing_date: "2025-01-05",
      reasoning: "Annual subscription renewal with clear billing information"
    }
  },
  {
    input: `From: newsletter@techcrunch.com
Subject: This week in tech: AI breakthrough
Body: Welcome to this week's newsletter. Here are the top stories...`,
    output: {
      is_subscription: false,
      confidence_score: 0.95,
      reasoning: "Free newsletter without any payment or billing information"
    }
  },
  {
    input: `From: support@spotify.com
Subject: Your free trial is ending soon
Body: Your Spotify Premium free trial ends in 3 days. After that, you'll be charged $9.99/month. Cancel anytime in your account settings.`,
    output: {
      is_subscription: true,
      confidence_score: 0.85,
      vendor_name: "Spotify",
      vendor_email: "support@spotify.com",
      amount: 9.99,
      currency: "USD",
      billing_cycle: "monthly",
      reasoning: "Free trial ending with upcoming recurring charge"
    }
  }
];

export function buildEnhancedPrompt(email: EmailData): string {
  const exampleSection = FEW_SHOT_EXAMPLES.map((example, i) => 
    `Example ${i + 1}:
Input: ${example.input}
Output: ${JSON.stringify(example.output, null, 2)}`
  ).join('\n\n');

  return `${SUBSCRIPTION_DETECTION_SYSTEM_PROMPT}

Here are some examples of how to analyze emails:

${exampleSection}

Now analyze this email:

Email Data:
From: ${email.sender}
Subject: ${email.subject}
Date: ${email.receivedAt.toISOString()}
Body: ${email.body.substring(0, 1500)}

Instructions:
- Look for recurring charges, subscriptions, memberships, renewals, or regular billing
- Check for mentions of billing cycles (monthly, yearly, weekly)
- Identify subscription amounts and next billing dates
- Ignore one-time purchases unless they mention future recurring billing
- Ignore newsletters or marketing emails without payment information
- Ignore social media notifications, calendar invites, or personal emails
- Be conservative - only mark as subscription if you're confident (confidence >= 0.7)
- Extract exact amounts and dates when possible

Response format (JSON):
{
  "is_subscription": boolean,
  "confidence_score": 0.0-1.0,
  "vendor_name": "string or null",
  "vendor_email": "string or null", 
  "amount": number or null,
  "currency": "USD/EUR/GBP/etc or null",
  "billing_cycle": "monthly/yearly/weekly/one-time or null",
  "next_billing_date": "YYYY-MM-DD or null",
  "reasoning": "brief explanation of why this is or isn't a subscription"
}`;
}

export function buildQuickCheckPrompt(email: EmailData): string {
  return `Quickly determine if this email is about a subscription service (yes/no):

From: ${email.sender}
Subject: ${email.subject}

Look for keywords like: subscription, billing, renewal, membership, recurring, charged, payment.
Response: {{"is_likely_subscription": true/false}}`;
}