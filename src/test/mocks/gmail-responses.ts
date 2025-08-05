/**
 * Mock Gmail API responses for testing
 */

import { gmail_v1 } from 'googleapis';

/**
 * Creates a mock message list response
 */
export function createMockMessageList(count: number = 10): gmail_v1.Schema$ListMessagesResponse {
  const messages: gmail_v1.Schema$Message[] = [];
  
  for (let i = 0; i < count; i++) {
    messages.push({
      id: `msg_${i + 1}`,
      threadId: `thread_${Math.floor(i / 2) + 1}`
    });
  }
  
  return {
    messages,
    resultSizeEstimate: count,
    nextPageToken: count >= 100 ? 'next_page_token' : undefined
  };
}

/**
 * Creates a mock full message response
 */
export function createMockMessage(
  id: string,
  subject: string,
  sender: string,
  body: string,
  receivedDate: Date = new Date()
): gmail_v1.Schema$Message {
  return {
    id,
    threadId: `thread_${id}`,
    labelIds: ['INBOX', 'UNREAD'],
    snippet: body.substring(0, 100),
    historyId: '12345',
    internalDate: receivedDate.getTime().toString(),
    payload: {
      mimeType: 'multipart/alternative',
      headers: [
        { name: 'Subject', value: subject },
        { name: 'From', value: sender },
        { name: 'To', value: 'user@example.com' },
        { name: 'Date', value: receivedDate.toUTCString() }
      ],
      parts: [
        {
          mimeType: 'text/plain',
          body: {
            data: Buffer.from(body).toString('base64url'),
            size: body.length
          }
        },
        {
          mimeType: 'text/html',
          body: {
            data: Buffer.from(`<html><body>${body}</body></html>`).toString('base64url'),
            size: body.length + 25
          }
        }
      ]
    }
  };
}

/**
 * Creates mock subscription emails
 */
export const mockSubscriptionEmails = {
  netflix: createMockMessage(
    'netflix_1',
    'Your Netflix subscription has been renewed',
    'Netflix <info@netflix.com>',
    `Dear Customer,

Your Netflix subscription has been successfully renewed for another month.

Plan: Premium
Amount: $19.99
Next billing date: March 15, 2024

Thank you for being a Netflix member!

The Netflix Team`,
    new Date('2024-02-15')
  ),

  spotify: createMockMessage(
    'spotify_1',
    'Spotify Premium - Payment Received',
    'Spotify <no-reply@spotify.com>',
    `Hi there!

We've received your payment for Spotify Premium.

Amount paid: $9.99
Billing period: Feb 1 - Feb 28, 2024
Payment method: •••• 1234

Keep enjoying your music!

Spotify`,
    new Date('2024-02-01')
  ),

  github: createMockMessage(
    'github_1',
    'GitHub Pro subscription renewed',
    'GitHub <noreply@github.com>',
    `Your GitHub Pro subscription has been renewed.

Subscription: GitHub Pro
Amount: $4.00 USD
Period: Monthly
Next renewal: March 10, 2024

View your billing settings: https://github.com/settings/billing

Thanks,
The GitHub Team`,
    new Date('2024-02-10')
  ),

  newsletter: createMockMessage(
    'newsletter_1',
    'Weekly Newsletter - Top Stories',
    'Newsletter <newsletter@example.com>',
    `Here are this week's top stories:

1. Breaking news story
2. Technology update
3. Sports highlights

This is a free newsletter. No payment required.

Unsubscribe: https://example.com/unsubscribe`,
    new Date('2024-02-12')
  ),

  receipt: createMockMessage(
    'receipt_1',
    'Your Amazon order has shipped',
    'Amazon <ship-confirm@amazon.com>',
    `Your order has shipped!

Order #123-4567890
Items: Laptop Stand
Total: $29.99

This is a one-time purchase, not a subscription.

Track your package: https://amazon.com/track`,
    new Date('2024-02-13')
  )
};

/**
 * Creates a mock history response
 */
export function createMockHistory(
  messageIds: string[]
): gmail_v1.Schema$ListHistoryResponse {
  const history: gmail_v1.Schema$History[] = messageIds.map(id => ({
    id: `history_${id}`,
    messagesAdded: [{
      message: {
        id,
        threadId: `thread_${id}`,
        labelIds: ['INBOX']
      }
    }]
  }));

  return {
    history,
    historyId: '67890'
  };
}

/**
 * Mock Gmail service for testing
 */
export class MockGmailService {
  private messages: Map<string, gmail_v1.Schema$Message> = new Map();

  constructor() {
    // Add default mock messages
    Object.entries(mockSubscriptionEmails).forEach(([key, message]) => {
      this.messages.set(message.id!, message);
    });
  }

  async getMessageList(options: any = {}) {
    const allMessages = Array.from(this.messages.values());
    const maxResults = options.maxResults || 100;
    
    return {
      messages: allMessages.slice(0, maxResults).map(m => ({
        id: m.id,
        threadId: m.threadId
      }))
    };
  }

  async getMessage(messageId: string) {
    const message = this.messages.get(messageId);
    if (!message) {
      throw new Error(`Message ${messageId} not found`);
    }
    return message;
  }

  addMockMessage(message: gmail_v1.Schema$Message) {
    this.messages.set(message.id!, message);
  }

  clearMessages() {
    this.messages.clear();
  }
}