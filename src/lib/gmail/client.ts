import { google, gmail_v1 } from 'googleapis';
import { OAuth2Client } from 'google-auth-library';
import { createAuthenticatedClient } from '../auth/google-oauth';
import { decryptToken } from '../auth/token-manager';
import type { GmailConnection } from './types';

/**
 * Gmail API client initialization and management
 */

/**
 * Creates Gmail API client from connection
 * @param connection - Database connection with encrypted tokens
 * @returns Configured Gmail API client
 */
export function createGmailClient(connection: GmailConnection): gmail_v1.Gmail {
  // Decrypt tokens
  const accessToken = decryptToken(connection.accessToken);
  const refreshToken = decryptToken(connection.refreshToken);
  
  // Create authenticated OAuth client
  const oauth2Client = createAuthenticatedClient(accessToken, refreshToken);
  
  // Create Gmail API client
  return google.gmail({ version: 'v1', auth: oauth2Client });
}

/**
 * Creates Gmail API client from OAuth2Client
 * @param oauth2Client - Authenticated OAuth2Client
 * @returns Configured Gmail API client
 */
export function createGmailClientFromAuth(oauth2Client: OAuth2Client): gmail_v1.Gmail {
  return google.gmail({ version: 'v1', auth: oauth2Client });
}

/**
 * Validates Gmail API access
 * @param gmail - Gmail API client
 * @returns true if access is valid
 */
export async function validateGmailAccess(gmail: gmail_v1.Gmail): Promise<boolean> {
  try {
    // Try to get user profile to validate access
    const response = await gmail.users.getProfile({ userId: 'me' });
    return !!response.data.emailAddress;
  } catch (error) {
    console.error('Gmail access validation failed:', error);
    return false;
  }
}

/**
 * Gets user email address from Gmail
 * @param gmail - Gmail API client
 * @returns User's email address
 */
export async function getUserEmail(gmail: gmail_v1.Gmail): Promise<string> {
  const response = await gmail.users.getProfile({ userId: 'me' });
  
  if (!response.data.emailAddress) {
    throw new Error('Unable to retrieve email address from Gmail');
  }
  
  return response.data.emailAddress;
}

/**
 * Gets current history ID for incremental sync
 * @param gmail - Gmail API client
 * @returns Current history ID
 */
export async function getCurrentHistoryId(gmail: gmail_v1.Gmail): Promise<string> {
  // Get a recent message to obtain history ID
  const response = await gmail.users.messages.list({
    userId: 'me',
    maxResults: 1
  });
  
  if (!response.data.messages || response.data.messages.length === 0) {
    throw new Error('No messages found to obtain history ID');
  }
  
  // Get full message to obtain history ID
  const message = await gmail.users.messages.get({
    userId: 'me',
    id: response.data.messages[0].id!,
    format: 'minimal'
  });
  
  if (!message.data.historyId) {
    throw new Error('Unable to obtain history ID');
  }
  
  return message.data.historyId;
}