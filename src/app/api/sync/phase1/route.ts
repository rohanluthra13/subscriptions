import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { eq } from 'drizzle-orm';
import { db } from '@/lib/db';
import { connections, processedEmails, syncJobs } from '@/lib/db/schema';
import { createGmailClient } from '@/lib/gmail/client';
import { gmail_v1 } from 'googleapis';

// Phase 1: Email Metadata Ingestion
// Fetches email metadata from Gmail and stores in processed_emails table

const phase1Schema = z.object({
  limit: z.number().min(1).max(1000).default(30),
  connectionId: z.string().optional()
});

interface Phase1Request {
  limit?: number;
  connectionId?: string;
}

interface Phase1Response {
  success: boolean;
  emailsFetched: number;
  newEmails: number;
  duplicates: number;
  processingTimeMs: number;
  message: string;
}

export async function POST(request: NextRequest) {
  const startTime = Date.now();
  
  try {
    // Parse request body
    const body: Phase1Request = await request.json();
    const { limit, connectionId } = phase1Schema.parse(body);

    // Get active Gmail connection
    let connection;
    if (connectionId) {
      const result = await db
        .select()
        .from(connections)
        .where(eq(connections.id, connectionId))
        .limit(1);
      connection = result[0];
    } else {
      // Get first active connection (single-user MVP)
      const result = await db
        .select()
        .from(connections)
        .where(eq(connections.isActive, true))
        .limit(1);
      connection = result[0];
    }

    if (!connection) {
      return NextResponse.json(
        { error: 'No active Gmail connection found' },
        { status: 404 }
      );
    }

    // Create Gmail client
    const gmail = createGmailClient({
      id: connection.id,
      userId: connection.userId,
      email: connection.email,
      accessToken: connection.accessToken,
      refreshToken: connection.refreshToken,
      tokenExpiry: connection.tokenExpiry,
      historyId: connection.historyId || undefined,
      lastSyncAt: connection.lastSyncAt || undefined,
      isActive: connection.isActive || true
    });

    console.log(`Phase 1: Fetching ${limit} email metadata for connection ${connection.id}`);

    // Fetch email list from Gmail
    const emailMetadata = await fetchEmailMetadata(gmail, limit);
    
    console.log(`Phase 1: Fetched ${emailMetadata.length} emails from Gmail`);

    // Store metadata in database
    const storageResult = await storeEmailMetadata(emailMetadata, connection.id);

    // Log sync job for audit trail
    await db.insert(syncJobs).values({
      connectionId: connection.id,
      jobType: 'fetch_emails',
      status: 'completed',
      totalEmails: emailMetadata.length,
      processedEmails: storageResult.newEmails,
      startedAt: new Date(startTime),
      completedAt: new Date()
    });

    const response: Phase1Response = {
      success: true,
      emailsFetched: emailMetadata.length,
      newEmails: storageResult.newEmails,
      duplicates: storageResult.duplicates,
      processingTimeMs: Date.now() - startTime,
      message: `Phase 1 complete: ${storageResult.newEmails} new emails stored, ${storageResult.duplicates} duplicates skipped`
    };

    console.log('Phase 1 complete:', response);
    return NextResponse.json(response);

  } catch (error) {
    console.error('Phase 1 failed:', error);
    return NextResponse.json(
      { 
        error: 'Phase 1 failed', 
        details: error instanceof Error ? error.message : 'Unknown error',
        processingTimeMs: Date.now() - startTime
      },
      { status: 500 }
    );
  }
}

async function fetchEmailMetadata(gmail: gmail_v1.Gmail, limit: number) {
  const emailMetadata = [];
  
  // Fetch email list from Gmail API
  const response = await gmail.users.messages.list({
    userId: 'me',
    maxResults: limit,
    q: '-in:sent -in:spam -in:trash' // All received emails excluding sent, spam, trash
  });

  if (!response.data.messages) {
    return [];
  }

  // Get metadata for each email
  for (const message of response.data.messages) {
    if (!message.id) continue;

    try {
      // Fetch minimal metadata (not full content)
      const emailResponse = await gmail.users.messages.get({
        userId: 'me',
        id: message.id,
        format: 'metadata',
        metadataHeaders: ['Subject', 'From', 'Date']
      });

      const headers = emailResponse.data.payload?.headers || [];
      const subject = getHeader(headers, 'Subject') || '';
      const sender = getHeader(headers, 'From') || '';
      const dateHeader = getHeader(headers, 'Date') || '';
      
      // Parse date
      let receivedAt: Date;
      try {
        receivedAt = dateHeader ? new Date(dateHeader) : new Date(parseInt(emailResponse.data.internalDate || '0'));
      } catch {
        receivedAt = new Date();
      }

      emailMetadata.push({
        gmailMessageId: message.id,
        gmailThreadId: message.threadId || null,
        subject,
        sender,
        receivedAt
      });

    } catch (error) {
      console.error(`Failed to fetch metadata for email ${message.id}:`, error);
      // Continue processing other emails
    }
  }

  return emailMetadata;
}

async function storeEmailMetadata(emailMetadata: any[], connectionId: string) {
  let newEmails = 0;
  let duplicates = 0;

  for (const email of emailMetadata) {
    try {
      // Check if email already exists
      const existing = await db
        .select()
        .from(processedEmails)
        .where(eq(processedEmails.gmailMessageId, email.gmailMessageId))
        .limit(1);

      if (existing.length > 0) {
        duplicates++;
        continue;
      }

      // Insert new email metadata
      await db.insert(processedEmails).values({
        connectionId,
        gmailMessageId: email.gmailMessageId,
        gmailThreadId: email.gmailThreadId,
        subject: email.subject,
        sender: email.sender,
        receivedAt: email.receivedAt,
        fetchedAt: new Date(),
        // Phase 1: No processing yet
        isSubscription: false,
        subscriptionId: null,
        confidenceScore: null,
        processingError: null
      });

      newEmails++;

    } catch (error) {
      console.error(`Failed to store email ${email.gmailMessageId}:`, error);
      // Continue processing other emails
    }
  }

  return { newEmails, duplicates };
}

function getHeader(headers: gmail_v1.Schema$MessagePartHeader[], name: string): string | undefined {
  return headers.find(h => h.name?.toLowerCase() === name.toLowerCase())?.value || undefined;
}