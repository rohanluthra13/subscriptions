import { NextRequest, NextResponse } from 'next/server';
import { generateAuthUrl, generateState, validateOAuthConfig } from '@/lib/auth/google-oauth';

/**
 * POST /api/auth/gmail/connect
 * Initiates Gmail OAuth flow
 */
export async function POST(request: NextRequest) {
  try {
    // Validate OAuth configuration
    if (!validateOAuthConfig()) {
      return NextResponse.json(
        { 
          error: {
            code: 'CONFIG_ERROR',
            message: 'Google OAuth is not properly configured. Please check environment variables.'
          }
        },
        { status: 500 }
      );
    }

    // Parse optional redirect URI from request
    const body = await request.json().catch(() => ({}));
    const redirectUri = body.redirect_uri;

    // Generate CSRF protection state
    const state = generateState();

    // Store state in a secure HTTP-only cookie for validation
    const response = NextResponse.json({
      auth_url: generateAuthUrl(state),
      state: state
    });

    // Set state cookie for CSRF validation (expires in 10 minutes)
    response.cookies.set('oauth_state', state, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 600 // 10 minutes
    });

    return response;
  } catch (error) {
    console.error('OAuth initiation failed:', error);
    
    return NextResponse.json(
      { 
        error: {
          code: 'OAUTH_INIT_FAILED',
          message: 'Failed to initiate OAuth flow',
          details: error instanceof Error ? error.message : 'Unknown error'
        }
      },
      { status: 500 }
    );
  }
}

/**
 * GET /api/auth/gmail/connect
 * Returns OAuth configuration status
 */
export async function GET() {
  const isConfigured = validateOAuthConfig();
  
  return NextResponse.json({
    configured: isConfigured,
    message: isConfigured 
      ? 'OAuth is properly configured' 
      : 'OAuth configuration is incomplete. Check environment variables.'
  });
}