import { gmail_v1 } from 'googleapis';
import { 
  createGmailClient, 
  getCurrentHistoryId 
} from './client';
import { 
  getHeader, 
  extractBody, 
  buildGmailQuery, 
  getHistoricalDate,
  extractEmailAddress 
} from './utils';
import type { 
  EmailData, 
  EmailMetadata, 
  GmailConnection, 
  MessageListOptions,
  HistoricalEmailOptions,
  BatchFetchResult,
  isRateLimitError,
  isAuthError
} from './types';

/**
 * Gmail Service for email fetching and processing
 * Implements on-demand fetching as per DESIGN.md
 */
export class GmailService {
  private gmail: gmail_v1.Gmail;
  private connection: GmailConnection;

  constructor(connection: GmailConnection) {
    this.connection = connection;
    this.gmail = createGmailClient(connection);
  }

  /**
   * Get email metadata list (IDs only, no content)
   * Used for batch processing to minimize API calls
   */
  async getMessageList(options: MessageListOptions = {}): Promise<EmailMetadata[]> {
    const query = options.query || buildGmailQuery({ includeSpamTrash: false });
    const messages: EmailMetadata[] = [];
    let pageToken: string | undefined = options.pageToken;

    try {
      do {
        const response = await this.withRetry(() =>
          this.gmail.users.messages.list({
            userId: 'me',
            maxResults: options.maxResults || 100,
            pageToken,
            q: query
          })
        );

        if (response.data.messages) {
          messages.push(...response.data.messages.map(msg => ({
            id: msg.id!,
            threadId: msg.threadId || undefined
          })));
        }

        pageToken = response.data.nextPageToken || undefined;
        
        // Stop if we've reached the desired number of results
        if (options.maxResults && messages.length >= options.maxResults) {
          break;
        }
      } while (pageToken);

      return messages.slice(0, options.maxResults);
    } catch (error) {
      console.error('Failed to fetch message list:', error);
      throw error;
    }
  }

  /**
   * Fetch full email content on-demand
   * Called when processing individual emails
   */
  async getMessage(messageId: string): Promise<EmailData> {
    try {
      const response = await this.withRetry(() =>
        this.gmail.users.messages.get({
          userId: 'me',
          id: messageId,
          format: 'full'
        })
      );

      const message = response.data;
      const headers = message.payload?.headers || [];
      
      return {
        id: messageId,
        threadId: message.threadId || undefined,
        subject: getHeader(headers, 'Subject') || '',
        sender: getHeader(headers, 'From') || '',
        body: extractBody(message.payload),
        receivedAt: new Date(parseInt(message.internalDate || '0')),
        labels: message.labelIds || [],
        snippet: message.snippet || undefined
      };
    } catch (error) {
      console.error(`Failed to fetch message ${messageId}:`, error);
      throw error;
    }
  }

  /**
   * Get historical emails for onboarding (30 days default)
   * Returns only message IDs for processing
   */
  async getHistoricalEmails(options: HistoricalEmailOptions = {}): Promise<string[]> {
    const months = options.months || 1;
    const since = getHistoricalDate(months);
    
    const query = buildGmailQuery({
      since,
      additionalQuery: options.query
    });

    const messages = await this.getMessageList({
      query,
      maxResults: options.maxResults || 5000 // Reasonable limit for onboarding
    });

    return messages.map(m => m.id);
  }

  /**
   * Get emails since a specific date (for incremental sync)
   * Uses last_sync_at timestamp
   */
  async getEmailsSince(since: Date): Promise<string[]> {
    const query = buildGmailQuery({ since });
    
    const messages = await this.getMessageList({
      query,
      maxResults: 500 // Reasonable limit for daily sync
    });

    return messages.map(m => m.id);
  }

  /**
   * Batch fetch multiple emails with error handling
   * Processes in batches of 50 as per DESIGN.md
   */
  async batchFetchEmails(messageIds: string[]): Promise<BatchFetchResult> {
    const batchSize = 50; // Gmail API batch limit from DESIGN.md
    const result: BatchFetchResult = {
      successful: [],
      failed: []
    };

    // Process in batches
    for (let i = 0; i < messageIds.length; i += batchSize) {
      const batch = messageIds.slice(i, i + batchSize);
      
      // Fetch emails in parallel within batch
      const promises = batch.map(async (id) => {
        try {
          const email = await this.getMessage(id);
          return { success: true, data: email };
        } catch (error) {
          return { 
            success: false, 
            id, 
            error: error instanceof Error ? error : new Error('Unknown error') 
          };
        }
      });

      const results = await Promise.all(promises);
      
      // Separate successful and failed fetches
      for (const res of results) {
        if (res.success && 'data' in res && res.data) {
          result.successful.push(res.data);
        } else if (!res.success && 'id' in res && res.id && res.error) {
          result.failed.push({ id: res.id, error: res.error });
        }
      }

      // Add small delay between batches to avoid rate limiting
      if (i + batchSize < messageIds.length) {
        await this.delay(100);
      }
    }

    return result;
  }

  /**
   * Use Gmail History API for incremental sync
   * More efficient than fetching all messages
   */
  async getHistoryList(startHistoryId: string): Promise<string[]> {
    const messageIds = new Set<string>();
    let pageToken: string | undefined;

    try {
      do {
        const response = await this.withRetry(() =>
          this.gmail.users.history.list({
            userId: 'me',
            startHistoryId,
            labelId: 'INBOX',
            pageToken
          })
        );

        if (response.data.history) {
          for (const history of response.data.history) {
            // Collect message IDs from history
            if (history.messagesAdded) {
              for (const added of history.messagesAdded) {
                if (added.message?.id) {
                  messageIds.add(added.message.id);
                }
              }
            }
          }
        }

        pageToken = response.data.nextPageToken || undefined;
      } while (pageToken);

      return Array.from(messageIds);
    } catch (error: any) {
      // If history is too old or invalid, fall back to date-based sync
      if (error.code === 404 || error.message?.includes('historyId')) {
        console.log('History ID invalid, falling back to date-based sync');
        return this.getEmailsSince(this.connection.lastSyncAt || getHistoricalDate(1));
      }
      throw error;
    }
  }

  /**
   * Update connection's history ID after successful sync
   */
  async updateHistoryId(): Promise<string> {
    try {
      const historyId = await getCurrentHistoryId(this.gmail);
      // This should trigger a database update in the calling service
      return historyId;
    } catch (error) {
      console.error('Failed to update history ID:', error);
      throw error;
    }
  }

  /**
   * Retry logic with exponential backoff for rate limiting
   * As specified in DESIGN.md
   */
  private async withRetry<T>(
    operation: () => Promise<T>,
    maxRetries: number = 3
  ): Promise<T> {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error: any) {
        const isRateLimit = error.code === 429 || 
                          (error.code === 403 && error.message?.includes('quota'));
        
        if (isRateLimit && attempt < maxRetries) {
          // Exponential backoff: 2^attempt * 1000ms
          const delay = Math.pow(2, attempt) * 1000;
          console.log(`Rate limited, retrying after ${delay}ms (attempt ${attempt}/${maxRetries})`);
          await this.delay(delay);
          continue;
        }
        
        throw error;
      }
    }
    
    throw new Error('Max retries exceeded');
  }

  /**
   * Helper function for delays
   */
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Get user's email address from Gmail profile
   */
  async getUserEmail(): Promise<string> {
    const response = await this.gmail.users.getProfile({ userId: 'me' });
    return response.data.emailAddress || '';
  }
}