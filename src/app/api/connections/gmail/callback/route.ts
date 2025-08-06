import { NextRequest } from 'next/server';
import { redirect } from 'next/navigation';
import { exchangeCodeForTokens } from '@/lib/auth/google-oauth';
import { encryptToken } from '@/lib/auth/token-manager';
import { createGmailClientFromAuth, getUserEmail } from '@/lib/gmail/client';
import { db } from '@/lib/db';
import { connections } from '@/lib/db/schema';
import { eq } from 'drizzle-orm';
import { ApiError, ErrorCode } from '@/lib/api/types/errors';
import type { CallbackResponse } from '@/lib/api/types/responses';

// In-memory state store (should match the one in route.ts)
// In production, this should be shared via Redis or database
const stateStore = new Map<string, { timestamp: number; redirectUri?: string }>();

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const error = searchParams.get('error');
  
  // Handle OAuth errors
  if (error) {
    console.error('OAuth error:', error);
    return redirect(`/?error=${encodeURIComponent(error)}`);
  }
  
  if (!code || !state) {
    return redirect('/?error=missing_parameters');
  }
  
  // Verify state for CSRF protection
  const stateData = stateStore.get(state);
  if (!stateData) {
    return redirect('/?error=invalid_state');
  }
  
  // Remove used state
  stateStore.delete(state);
  
  // Check if state is expired (10 minutes)
  if (Date.now() - stateData.timestamp > 10 * 60 * 1000) {
    return redirect('/?error=state_expired');
  }
  
  try {
    // Exchange code for tokens
    const tokens = await exchangeCodeForTokens(code);
    
    // Create authenticated Gmail client to get user email
    const oauth2Client = await import('@/lib/auth/google-oauth').then(m => 
      m.createAuthenticatedClient(tokens.accessToken, tokens.refreshToken)
    );
    const gmail = createGmailClientFromAuth(oauth2Client);
    const userEmail = await getUserEmail(gmail);
    
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
          isActive: true,
          updatedAt: new Date(),
        })
        .where(eq(connections.id, existingConnection[0].id))
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
          isActive: true,
        })
        .returning();
      
      connectionId = created.id;
    }
    
    // Redirect to success page or custom redirect URI
    const redirectUri = stateData.redirectUri || '/';
    return redirect(`${redirectUri}?success=true&connection_id=${connectionId}`);
    
  } catch (error) {
    console.error('OAuth callback error:', error);
    return redirect(`/?error=${encodeURIComponent('Failed to connect Gmail')}`);
  }
}