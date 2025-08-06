import { EmailData, SubscriptionData, ProcessingResult, LLMProvider } from './types';
import { OpenAIProvider } from './openai';

export class SubscriptionDetector {
  private provider: LLMProvider;
  private processedCount = 0;
  private totalCost = 0;

  constructor(provider?: LLMProvider) {
    this.provider = provider || new OpenAIProvider();
  }

  async detectSubscription(email: EmailData): Promise<ProcessingResult> {
    const startTime = Date.now();
    
    try {
      if (!this.shouldProcessEmail(email)) {
        return {
          subscription: null,
          metrics: {
            inputTokens: 0,
            outputTokens: 0,
            totalTokens: 0,
            estimatedCost: 0,
          },
          processingTime: Date.now() - startTime,
        };
      }

      const subscription = await this.provider.detectSubscription(email);
      const processingTime = Date.now() - startTime;
      
      // Build the actual prompt that was sent to calculate accurate cost
      const inputText = this.buildPromptForCostEstimation(email);
      const outputText = JSON.stringify(subscription || {});
      const inputTokens = this.provider.estimateTokenUsage(inputText);
      const outputTokens = this.provider.estimateTokenUsage(outputText);
      
      // Use proper cost calculation with separate input/output rates
      const estimatedCost = this.calculateCost(inputTokens, outputTokens);
      
      this.processedCount++;
      this.totalCost += estimatedCost;
      
      return {
        subscription,
        metrics: {
          inputTokens,
          outputTokens,
          totalTokens: inputTokens + outputTokens,
          estimatedCost,
        },
        processingTime,
      };
    } catch (error) {
      return {
        subscription: null,
        metrics: {
          inputTokens: 0,
          outputTokens: 0,
          totalTokens: 0,
          estimatedCost: 0,
        },
        processingTime: Date.now() - startTime,
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  shouldProcessEmail(email: EmailData): boolean {
    const subject = email.subject.toLowerCase();
    const sender = email.sender.toLowerCase();
    const body = email.body.toLowerCase().substring(0, 500);
    
    const skipPatterns = [
      'unsubscribe successful',
      'unsubscribed',
      'newsletter',
      'promotional',
      'sale ends',
      'limited time offer',
      'deal of the day',
      'flash sale',
      'social media',
      'calendar invite',
      'meeting invitation',
      'password reset',
      'verify your email',
      'confirm your account',
      'shipping confirmation',
      'order shipped',
      'delivery update',
      'package delivered',
    ];
    
    const combinedText = `${subject} ${sender} ${body}`;
    if (skipPatterns.some(pattern => combinedText.includes(pattern))) {
      return false;
    }
    
    const priorityPatterns = [
      'subscription',
      'billing',
      'invoice',
      'receipt',
      'payment',
      'renewal',
      'charged',
      'auto-pay',
      'membership',
      'recurring',
      'monthly fee',
      'annual fee',
      'your plan',
      'subscription plan',
      'payment method',
      'next billing',
      'billing cycle',
      'renews on',
      'expires on',
      'trial ending',
      'free trial',
    ];
    
    return priorityPatterns.some(pattern => combinedText.includes(pattern));
  }

  getStats(): { processed: number; totalCost: number; avgCostPerEmail: number } {
    return {
      processed: this.processedCount,
      totalCost: this.totalCost,
      avgCostPerEmail: this.processedCount > 0 ? this.totalCost / this.processedCount : 0,
    };
  }

  resetStats(): void {
    this.processedCount = 0;
    this.totalCost = 0;
  }

  private calculateCost(inputTokens: number, outputTokens: number): number {
    const modelName = this.provider.getModelName();
    const pricing = this.getModelPricing(modelName);
    
    const inputCost = (inputTokens / 1000) * pricing.inputPer1k;
    const outputCost = (outputTokens / 1000) * pricing.outputPer1k;
    
    return inputCost + outputCost;
  }

  private getModelPricing(model: string): { inputPer1k: number; outputPer1k: number } {
    const pricing: Record<string, { inputPer1k: number; outputPer1k: number }> = {
      'gpt-4o-mini': { inputPer1k: 0.00015, outputPer1k: 0.0006 },
      'gpt-4o': { inputPer1k: 0.0025, outputPer1k: 0.01 },
      'gpt-4-turbo': { inputPer1k: 0.01, outputPer1k: 0.03 },
    };
    
    return pricing[model] || pricing['gpt-4o-mini'];
  }

  private buildPromptForCostEstimation(email: EmailData): string {
    // This should match the actual prompt structure used by the provider
    // For now, we'll estimate based on the email content
    return `From: ${email.sender}\nSubject: ${email.subject}\nBody: ${email.body.substring(0, 1500)}`;
  }
}