import { OAuth2Client } from 'google-auth-library';
import crypto from 'crypto';

/**
 * Google OAuth configuration and helpers
 * Manages OAuth flow for Gmail API access
 */

// Gmail OAuth scopes as defined in DESIGN.md
export const GMAIL_SCOPES = [
  'https://www.googleapis.com/auth/gmail.readonly',
  'https://www.googleapis.com/auth/userinfo.email'
];

/**
 * Creates and configures OAuth2 client
 * @param redirectUri - Optional redirect URI override
 * @returns Configured OAuth2Client instance
 */
export function createOAuth2Client(redirectUri?: string): OAuth2Client {
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
  
  if (!clientId || !clientSecret) {
    throw new Error('Google OAuth credentials not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.');
  }

  const defaultRedirectUri = `${process.env.NEXTAUTH_URL || 'http://localhost:3000'}/api/auth/gmail/callback`;
  
  return new OAuth2Client(
    clientId,
    clientSecret,
    redirectUri || defaultRedirectUri
  );
}

/**
 * Generates OAuth authorization URL
 * @param state - CSRF protection state parameter
 * @returns Authorization URL for user consent
 */
export function generateAuthUrl(state: string): string {
  const oauth2Client = createOAuth2Client();
  
  return oauth2Client.generateAuthUrl({
    access_type: 'offline', // Required for refresh token
    scope: GMAIL_SCOPES,
    state: state,
    prompt: 'consent' // Force consent to ensure refresh token
  });
}

/**
 * Exchanges authorization code for tokens
 * @param code - Authorization code from OAuth callback
 * @returns Access and refresh tokens
 */
export async function exchangeCodeForTokens(code: string) {
  const oauth2Client = createOAuth2Client();
  
  const { tokens } = await oauth2Client.getToken(code);
  
  if (!tokens.access_token || !tokens.refresh_token) {
    throw new Error('Failed to obtain required tokens from Google');
  }
  
  // Get user info
  oauth2Client.setCredentials(tokens);
  
  // Calculate token expiry timestamp
  const tokenExpiry = tokens.expiry_date 
    ? new Date(tokens.expiry_date)
    : new Date(Date.now() + 3600 * 1000); // Default 1 hour if not provided
  
  return {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    tokenExpiry,
    scope: tokens.scope,
    tokenType: tokens.token_type || 'Bearer'
  };
}

/**
 * Creates OAuth2Client with existing tokens
 * @param accessToken - Current access token
 * @param refreshToken - Refresh token for renewal
 * @returns Configured OAuth2Client with tokens
 */
export function createAuthenticatedClient(
  accessToken: string,
  refreshToken: string
): OAuth2Client {
  const oauth2Client = createOAuth2Client();
  
  oauth2Client.setCredentials({
    access_token: accessToken,
    refresh_token: refreshToken
  });
  
  // Set up automatic token refresh
  oauth2Client.on('tokens', (tokens) => {
    if (tokens.refresh_token) {
      // New refresh token received, should update in database
      console.log('New refresh token received - update required');
    }
  });
  
  return oauth2Client;
}

/**
 * Validates OAuth configuration
 * @returns true if OAuth is properly configured
 */
export function validateOAuthConfig(): boolean {
  return !!(
    process.env.GOOGLE_CLIENT_ID &&
    process.env.GOOGLE_CLIENT_SECRET &&
    process.env.NEXTAUTH_URL
  );
}

/**
 * Generates a secure random state parameter for CSRF protection
 * @returns Random state string
 */
export function generateState(): string {
  return Buffer.from(crypto.randomUUID()).toString('base64url');
}