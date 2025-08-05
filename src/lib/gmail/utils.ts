import { gmail_v1 } from 'googleapis';

/**
 * Gmail utility functions for parsing and decoding email data
 */

/**
 * Extracts a header value from email headers
 * @param headers - Array of email headers
 * @param name - Header name to find (case-insensitive)
 * @returns Header value or undefined if not found
 */
export function getHeader(
  headers: gmail_v1.Schema$MessagePartHeader[],
  name: string
): string | undefined {
  const header = headers.find(
    h => h.name?.toLowerCase() === name.toLowerCase()
  );
  return header?.value || undefined;
}

/**
 * Decodes base64url encoded email body
 * @param data - Base64url encoded string
 * @returns Decoded UTF-8 string
 */
export function decodeBody(data: string): string {
  if (!data) return '';
  
  try {
    // Gmail uses base64url encoding (- instead of +, _ instead of /)
    return Buffer.from(data, 'base64url').toString('utf8');
  } catch (error) {
    console.error('Failed to decode email body:', error);
    return '';
  }
}

/**
 * Extracts email body from message payload
 * Handles both single-part and multipart messages
 * @param payload - Gmail message payload
 * @returns Extracted email body text
 */
export function extractBody(payload?: gmail_v1.Schema$MessagePart): string {
  if (!payload) return '';

  // Handle multipart emails
  if (payload.parts && payload.parts.length > 0) {
    // Look for text/plain first (preferred)
    for (const part of payload.parts) {
      if (part.mimeType === 'text/plain' && part.body?.data) {
        return decodeBody(part.body.data);
      }
    }
    
    // Fall back to text/html if no plain text
    for (const part of payload.parts) {
      if (part.mimeType === 'text/html' && part.body?.data) {
        return stripHtml(decodeBody(part.body.data));
      }
    }
    
    // Recursively check nested parts (for complex multipart messages)
    for (const part of payload.parts) {
      if (part.parts) {
        const nestedBody = extractBody(part);
        if (nestedBody) return nestedBody;
      }
    }
  }

  // Handle single-part emails
  if (payload.body?.data) {
    const decoded = decodeBody(payload.body.data);
    
    // Strip HTML if needed
    if (payload.mimeType === 'text/html') {
      return stripHtml(decoded);
    }
    
    return decoded;
  }

  return '';
}

/**
 * Basic HTML stripping for email content
 * @param html - HTML content
 * @returns Plain text content
 */
export function stripHtml(html: string): string {
  // Remove script and style elements
  let text = html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  text = text.replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '');
  
  // Replace common HTML entities
  text = text.replace(/&nbsp;/gi, ' ');
  text = text.replace(/&amp;/gi, '&');
  text = text.replace(/&lt;/gi, '<');
  text = text.replace(/&gt;/gi, '>');
  text = text.replace(/&quot;/gi, '"');
  text = text.replace(/&#39;/gi, "'");
  
  // Replace line breaks
  text = text.replace(/<br\s*\/?>/gi, '\n');
  text = text.replace(/<\/p>/gi, '\n\n');
  text = text.replace(/<\/div>/gi, '\n');
  
  // Remove remaining HTML tags
  text = text.replace(/<[^>]+>/g, '');
  
  // Clean up whitespace
  text = text.replace(/\n{3,}/g, '\n\n');
  text = text.trim();
  
  return text;
}

/**
 * Builds Gmail search query for fetching emails
 * @param options - Query options
 * @returns Gmail search query string
 */
export function buildGmailQuery(options: {
  since?: Date;
  before?: Date;
  includeSpamTrash?: boolean;
  additionalQuery?: string;
}): string {
  const parts: string[] = [];
  
  // Default: exclude spam and trash
  if (!options.includeSpamTrash) {
    parts.push('-in:spam', '-in:trash');
  }
  
  // Add date filters
  if (options.since) {
    const sinceDate = options.since.toISOString().split('T')[0].replace(/-/g, '/');
    parts.push(`after:${sinceDate}`);
  }
  
  if (options.before) {
    const beforeDate = options.before.toISOString().split('T')[0].replace(/-/g, '/');
    parts.push(`before:${beforeDate}`);
  }
  
  // Add any additional query terms
  if (options.additionalQuery) {
    parts.push(options.additionalQuery);
  }
  
  // Default to inbox if no other location specified
  if (!options.additionalQuery?.includes('in:')) {
    parts.push('in:inbox');
  }
  
  return parts.join(' ');
}

/**
 * Parses sender email address from "Name <email>" format
 * @param sender - Sender string from email header
 * @returns Email address only
 */
export function extractEmailAddress(sender: string): string {
  const match = sender.match(/<([^>]+)>/);
  return match ? match[1] : sender;
}

/**
 * Calculates date for historical email fetch
 * @param months - Number of months to go back
 * @returns Date object for the calculated time
 */
export function getHistoricalDate(months: number): Date {
  const date = new Date();
  date.setMonth(date.getMonth() - months);
  return date;
}