import { NextRequest, NextResponse } from 'next/server';
import { exchangeCodeForTokens } from '@/lib/auth/google-oauth';
import { encryptToken } from '@/lib/auth/token-manager';
import { createGmailClientFromAuth, getUserEmail, getCurrentHistoryId } from '@/lib/gmail/client';
import { createOAuth2Client } from '@/lib/auth/google-oauth';
import { db } from '@/lib/db';
import { connections } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const error = searchParams.get('error');
  
  // Handle OAuth errors
  if (error) {
    console.error('OAuth error:', error);
    return NextResponse.redirect(
      `${process.env.NEXTAUTH_URL || 'http://localhost:3000'}/dashboard?error=oauth_denied`
    );
  }
  
  if (!code || !state) {
    return NextResponse.redirect(
      `${process.env.NEXTAUTH_URL || 'http://localhost:3000'}/dashboard?error=missing_params`
    );
  }
  
  // Verify state for CSRF protection using cookies
  const storedState = request.cookies.get('oauth_state')?.value;
  if (!storedState || storedState !== state) {
    console.error('State mismatch - possible CSRF attack');
    return NextResponse.redirect(
      `${process.env.NEXTAUTH_URL || 'http://localhost:3000'}/dashboard?error=invalid_state`
    );
  }
  
  try {
    // Exchange code for tokens
    const tokens = await exchangeCodeForTokens(code);
    
    // Create Gmail client to get user info
    const oauth2Client = createOAuth2Client();
    oauth2Client.setCredentials({
      access_token: tokens.accessToken,
      refresh_token: tokens.refreshToken
    });
    
    const gmail = createGmailClientFromAuth(oauth2Client);
    const userEmail = await getUserEmail(gmail);
    
    // Get initial history ID for incremental sync
    let historyId: string | undefined;
    try {
      historyId = await getCurrentHistoryId(gmail);
    } catch (error) {
      console.log('Could not get history ID, will use date-based sync');
    }
    
    // Check if connection already exists
    const existingConnection = await db
      .select()
      .from(connections)
      .where(eq(connections.email, userEmail))
      .limit(1);
    
    let connectionId: string;
    
    if (existingConnection.length > 0) {
      // Update existing connection
      const [updated] = await db
        .update(connections)
        .set({
          accessToken: encryptToken(tokens.accessToken),
          refreshToken: encryptToken(tokens.refreshToken),
          tokenExpiry: tokens.tokenExpiry,
          historyId: historyId,
          isActive: true,
          updatedAt: new Date(),
        })
        .where(eq(connections.email, userEmail))
        .returning();
      
      connectionId = updated.id;
    } else {
      // Create new connection
      const [created] = await db
        .insert(connections)
        .values({
          userId: '1', // Hardcoded for single-user MVP
          email: userEmail,
          accessToken: encryptToken(tokens.accessToken),
          refreshToken: encryptToken(tokens.refreshToken),
          tokenExpiry: tokens.tokenExpiry,
          historyId: historyId,
          isActive: true,
        })
        .returning();
      
      connectionId = created.id;
      console.log(`Created new connection for ${userEmail}, ID: ${connectionId}`);
    }
    
    console.log(`Final connection ID: ${connectionId}`);
    
    // Clear the state cookie and redirect to dashboard
    const response = NextResponse.redirect(
      `${process.env.NEXTAUTH_URL || 'http://localhost:3000'}/dashboard?success=true&connection=${connectionId}`
    );
    response.cookies.delete('oauth_state');
    
    return response;
    
  } catch (error) {
    console.error('OAuth callback error:', error);
    return NextResponse.redirect(
      `${process.env.NEXTAUTH_URL || 'http://localhost:3000'}/dashboard?error=callback_failed`
    );
  }
}