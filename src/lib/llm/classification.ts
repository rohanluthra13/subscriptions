import OpenAI from 'openai';
import { env } from '@/lib/env';

export interface EmailData {
  subject: string;
  sender: string;
  body: string;
  receivedAt: Date;
}

export interface ClassificationResult {
  isSubscription: boolean;
  vendor: string | null;
  emailType: string | null;
  confidence: number;
}

export class ClassificationService {
  private client: OpenAI;
  private model: string;

  constructor() {
    this.client = new OpenAI({
      apiKey: env.OPENAI_API_KEY,
      timeout: env.LLM_TIMEOUT_MS,
    });
    this.model = env.OPENAI_MODEL;
  }

  async classifyEmail(email: EmailData): Promise<ClassificationResult> {
    const prompt = this.buildClassificationPrompt(email);
    
    try {
      const response = await this.retryWithBackoff(async () => {
        return await this.client.chat.completions.create({
          model: this.model,
          messages: [
            {
              role: 'system',
              content: `You are part of a subscription management app. Your task is to individually screen the user's personal emails and identify if they relate to a subscription service. This may be a free or paid service. You have been given one email, and must give 3 responses in valid JSON in this exact structure:

{
  "is_subscription": boolean,
  "vendor_name": string or null,
  "email_type": string or null,
}

If is_subscription = false, then vendor_name = null , and email_type = null

Email type is important as it defines how the email relates to a subscription service.

If is_subscription = true, then email_type MUST be one of the following:  
  - payment - billing, charges, receipts
  - start - signups, trials, activations
  - stop - cancellations, account closures
  - pause - suspensions, pauses
  - change - plan changes, upgrades, downgrades
  - other - general content, offers, etc. 
 
As broad guidance on what is a subscription service:
Common subscription services include:
  - Streaming: Netflix, Amazon Prime, Disney+, Spotify
  - Productivity: Microsoft Office, GitHub, Figma, Slack, Adobe
  - AI: ChatGPT, Claude, Midjourney
  - Health: Gym memberships, meditation apps
  - News: The Economist, The Atlantic, NYT
  - Finance: Bank accounts, investment apps

Some common emails that are not subscriptions are typically:
  - Marketing/promotional emails
  - Shipping / tracking notifications`
            },
            {
              role: 'user',
              content: prompt
            }
          ],
          response_format: { type: 'json_object' },
          temperature: 0.1,
        });
      });

      if (!response.choices?.[0]?.message?.content) {
        throw new Error('Invalid OpenAI response');
      }

      const result = JSON.parse(response.choices[0].message.content);
      
      return {
        isSubscription: result.is_subscription || false,
        vendor: result.vendor_name || null,
        emailType: result.email_type || null,
        confidence: result.is_subscription ? 0.8 : 0.2 // Default confidence based on classification
      };

    } catch (error) {
      console.error('LLM classification failed:', error);
      
      // Return default non-subscription result on error
      return {
        isSubscription: false,
        vendor: null,
        emailType: null,
        confidence: 0
      };
    }
  }

  private buildClassificationPrompt(email: EmailData): string {
    // Truncate body to avoid token limits
    const maxBodyLength = 2000;
    const truncatedBody = email.body.length > maxBodyLength 
      ? email.body.substring(0, maxBodyLength) + '...[truncated]'
      : email.body;

    return `Analyze this email and determine if it's related to a subscription service:

Subject: ${email.subject}
From: ${email.sender}
Date: ${email.receivedAt.toISOString()}

Body:
${truncatedBody}`;
  }

  private async retryWithBackoff<T>(
    operation: () => Promise<T>,
    maxRetries: number = env.LLM_MAX_RETRIES
  ): Promise<T> {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error: any) {
        const isRetryable = error?.status === 429 || error?.status >= 500;
        
        if (!isRetryable || attempt === maxRetries) {
          throw error;
        }
        
        const delay = Math.pow(2, attempt) * 1000;
        console.log(`Retrying LLM call after ${delay}ms (attempt ${attempt}/${maxRetries})`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    throw new Error('Max retries exceeded');
  }
}