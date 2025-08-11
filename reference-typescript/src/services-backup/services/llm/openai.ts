import OpenAI from 'openai';
import { encoding_for_model, TiktokenModel } from 'tiktoken';
import { env } from '@/lib/env';
import { EmailData, LLMProvider, SubscriptionData, LLMResponse, CostMetrics } from './types';
import { buildEnhancedPrompt } from './prompts';

export class OpenAIProvider implements LLMProvider {
  private client: OpenAI;
  private model: string;
  private encoder: any;

  constructor() {
    this.client = new OpenAI({
      apiKey: env.OPENAI_API_KEY,
      timeout: env.LLM_TIMEOUT_MS,
    });
    this.model = env.OPENAI_MODEL;
    
    try {
      this.encoder = encoding_for_model(this.model as TiktokenModel);
    } catch {
      this.encoder = encoding_for_model('gpt-4');
    }
  }

  async detectSubscription(email: EmailData): Promise<SubscriptionData | null> {
    const prompt = buildEnhancedPrompt(email);
    
    try {
      const response = await this.retryWithBackoff(async () => {
        return await this.client.chat.completions.create({
          model: this.model,
          messages: [{ role: 'user', content: prompt }],
          response_format: { type: 'json_object' },
          temperature: 0.1,
          max_tokens: 500,
        });
      });

      // Add null checks for response structure
      if (!response.choices || response.choices.length === 0 || !response.choices[0].message) {
        console.error('Invalid OpenAI response structure');
        return null;
      }

      const result = JSON.parse(response.choices[0].message.content || '{}') as LLMResponse;
      
      if (result.is_subscription && result.confidence_score >= env.LLM_CONFIDENCE_THRESHOLD) {
        return this.transformResponse(result, email);
      }
      
      return null;
    } catch (error) {
      console.error('LLM detection failed:', error);
      throw new Error(`Subscription detection failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }

  estimateTokenUsage(text: string): number {
    try {
      return this.encoder.encode(text).length;
    } catch {
      return Math.ceil(text.length / 4);
    }
  }

  getModelName(): string {
    return this.model;
  }


  private transformResponse(response: LLMResponse, email: EmailData): SubscriptionData {
    // Validate and parse date safely
    let nextBillingDate: Date | undefined;
    if (response.next_billing_date) {
      const parsedDate = new Date(response.next_billing_date);
      // Check if date is valid
      if (!isNaN(parsedDate.getTime())) {
        nextBillingDate = parsedDate;
      } else {
        console.warn(`Invalid date received: ${response.next_billing_date}`);
      }
    }

    return {
      vendor_name: response.vendor_name || 'Unknown Vendor',
      vendor_email: response.vendor_email || email.sender,
      amount: response.amount || undefined,
      currency: response.currency || 'USD',
      billing_cycle: response.billing_cycle || undefined,
      next_billing_date: nextBillingDate,
      confidence_score: response.confidence_score,
      category: this.categorizeVendor(response.vendor_name || ''),
      status: 'active',
      renewal_type: response.billing_cycle === 'one-time' ? 'manual_renew' : 'auto_renew',
    };
  }

  private categorizeVendor(vendorName: string): string {
    const categories: Record<string, string[]> = {
      streaming: ['netflix', 'spotify', 'disney', 'hulu', 'amazon prime', 'youtube', 'apple tv', 'hbo'],
      software: ['adobe', 'microsoft', 'google', 'dropbox', 'github', 'slack', 'zoom', 'notion'],
      news: ['times', 'post', 'journal', 'news', 'magazine', 'reuters', 'bloomberg'],
      fitness: ['gym', 'fitness', 'peloton', 'strava', 'health', 'workout', 'yoga'],
      gaming: ['steam', 'playstation', 'xbox', 'nintendo', 'epic games', 'twitch'],
      food: ['hellofresh', 'doordash', 'uber eats', 'grubhub', 'instacart'],
    };

    const vendor = vendorName.toLowerCase();
    for (const [category, keywords] of Object.entries(categories)) {
      if (keywords.some(keyword => vendor.includes(keyword))) {
        return category;
      }
    }
    return 'other';
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
        console.log(`Retrying after ${delay}ms (attempt ${attempt}/${maxRetries})`);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
    
    throw new Error('Max retries exceeded');
  }

  async calculateCost(inputText: string, outputText: string): Promise<CostMetrics> {
    const inputTokens = this.estimateTokenUsage(inputText);
    const outputTokens = this.estimateTokenUsage(outputText);
    
    const pricing = this.getModelPricing();
    const inputCost = (inputTokens / 1000) * pricing.inputPer1k;
    const outputCost = (outputTokens / 1000) * pricing.outputPer1k;
    
    return {
      inputTokens,
      outputTokens,
      totalTokens: inputTokens + outputTokens,
      estimatedCost: inputCost + outputCost,
    };
  }

  private getModelPricing(): { inputPer1k: number; outputPer1k: number } {
    const pricing: Record<string, { inputPer1k: number; outputPer1k: number }> = {
      'gpt-4o-mini': { inputPer1k: 0.00015, outputPer1k: 0.0006 },
      'gpt-4o': { inputPer1k: 0.0025, outputPer1k: 0.01 },
      'gpt-4-turbo': { inputPer1k: 0.01, outputPer1k: 0.03 },
    };
    
    return pricing[this.model] || pricing['gpt-4o-mini'];
  }
}