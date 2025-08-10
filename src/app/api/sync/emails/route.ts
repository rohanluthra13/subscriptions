import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { eq, and, isNull, asc, sql, inArray } from 'drizzle-orm';
import { db } from '@/lib/db';
import { connections, processedEmails, syncJobs } from '@/lib/db/schema';
import { GmailService } from '@/lib/gmail/service';
import { ClassificationService } from '@/lib/llm/classification';
import { createGmailClient } from '@/lib/gmail/client';
import { gmail_v1 } from 'googleapis';

// Combined Phase 1 + Phase 2: Unified Email Sync & Classification
// Supports both "recent" and "older" sync modes with automatic classification

const syncEmailsSchema = z.object({
  mode: z.enum(['recent', 'older']).default('recent'),
  limit: z.number().min(1).max(500).default(30),
  autoClassify: z.boolean().default(true),
  connectionId: z.string().optional()
});

interface SyncEmailsRequest {
  mode?: 'recent' | 'older';
  limit?: number;
  autoClassify?: boolean;
  connectionId?: string;
}

interface SyncEmailsResponse {
  success: boolean;
  phase1: {
    emailsFetched: number;
    newEmails: number;
    duplicates: number;
  };
  phase2: {
    emailsProcessed: number;
    subscriptionsFound: number;
    errors: number;
  };
  processingTimeMs: number;
  hasMoreEmails: boolean;
  message: string;
}

export async function POST(request: NextRequest) {
  const startTime = Date.now();
  
  try {
    // Parse request body
    const body: SyncEmailsRequest = await request.json();
    const { mode, limit, autoClassify, connectionId } = syncEmailsSchema.parse(body);

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

    console.log(`Starting unified sync: mode=${mode}, limit=${limit}, autoClassify=${autoClassify}`);

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

    // PHASE 1: Fetch email metadata
    const phase1Result = await fetchEmailMetadata(gmail, connection, mode, limit);
    
    console.log(`Phase 1 complete: ${phase1Result.newEmails} new emails, ${phase1Result.duplicates} duplicates`);

    let phase2Result = {
      emailsProcessed: 0,
      subscriptionsFound: 0,
      errors: 0
    };

    // PHASE 2: Auto-classification (if enabled)
    if (autoClassify && phase1Result.newEmails > 0) {
      console.log(`Starting Phase 2: classifying ${phase1Result.newEmails} new emails`);
      
      // Get emails for classification - prefer specific IDs if available, otherwise fallback to unclassified
      let emailsToClassify: any[] = [];
      if (phase1Result.newEmailIds && phase1Result.newEmailIds.length > 0) {
        // Convert string IDs to proper format and validate
        const validIds = phase1Result.newEmailIds.filter(id => id && typeof id === 'string');
        if (validIds.length > 0) {
          emailsToClassify = await db
            .select()
            .from(processedEmails)
            .where(and(
              eq(processedEmails.connectionId, connection.id),
              inArray(processedEmails.id, validIds)
            ));
        } else {
          emailsToClassify = [];
        }
      } else {
        // Fallback: get recent unclassified emails
        emailsToClassify = await db
          .select()
          .from(processedEmails)
          .where(and(
            eq(processedEmails.connectionId, connection.id),
            isNull(processedEmails.classifiedAt)
          ))
          .limit(phase1Result.newEmails);
      }

      if (emailsToClassify.length > 0) {
        const gmailService = new GmailService({
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

        const classificationService = new ClassificationService();
        const classificationResult = await classifyEmails(emailsToClassify, gmailService, classificationService);
        phase2Result = {
          emailsProcessed: classificationResult.processed,
          subscriptionsFound: classificationResult.subscriptionsFound,
          errors: classificationResult.errors
        };
      }
    }

    // Log sync job for audit trail
    await db.insert(syncJobs).values({
      connectionId: connection.id,
      jobType: mode === 'recent' ? 'sync_recent' : 'sync_older',
      status: 'completed',
      totalEmails: phase1Result.emailsFetched,
      processedEmails: autoClassify ? phase2Result.emailsProcessed : phase1Result.newEmails,
      subscriptionsFound: phase2Result.subscriptionsFound,
      errorsCount: phase2Result.errors,
      startedAt: new Date(startTime),
      completedAt: new Date()
    });

    const response: SyncEmailsResponse = {
      success: true,
      phase1: {
        emailsFetched: phase1Result.emailsFetched,
        newEmails: phase1Result.newEmails,
        duplicates: phase1Result.duplicates
      },
      phase2: phase2Result,
      processingTimeMs: Date.now() - startTime,
      hasMoreEmails: phase1Result.hasMoreEmails,
      message: autoClassify 
        ? `Processed ${phase1Result.newEmails} emails, found ${phase2Result.subscriptionsFound} subscriptions`
        : `Fetched ${phase1Result.newEmails} new emails (classification disabled)`
    };

    console.log('Unified sync complete:', response);
    return NextResponse.json(response);

  } catch (error) {
    console.error('Unified sync failed:', error);
    return NextResponse.json(
      { 
        error: 'Unified sync failed', 
        details: error instanceof Error ? error.message : 'Unknown error',
        processingTimeMs: Date.now() - startTime
      },
      { status: 500 }
    );
  }
}

async function fetchEmailMetadata(
  gmail: gmail_v1.Gmail, 
  connection: any, 
  mode: 'recent' | 'older', 
  limit: number
) {
  const emailMetadata = [];
  let hasMoreEmails = false;
  let totalFetched = 0;

  // Build Gmail query based on sync mode
  let query: string;
  let pageToken: string | undefined;

  if (mode === 'recent') {
    // Get emails since last sync
    const since = connection.lastSyncAt || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000); // 30 days default
    const sinceStr = since.toISOString().split('T')[0]; // YYYY-MM-DD format
    query = `after:${sinceStr} -in:sent -in:spam -in:trash`;
    pageToken = undefined; // Always start fresh for recent
  } else {
    // Get older emails using date-based filtering
    // Find the oldest email we have and get emails before that date
    const oldestDate = await getOldestEmailDate(connection.id);
    if (oldestDate) {
      const beforeStr = oldestDate.toISOString().split('T')[0]; // YYYY-MM-DD format
      query = `before:${beforeStr} -in:sent -in:spam -in:trash`;
    } else {
      // No emails yet, get older emails without date filter
      query = '-in:sent -in:spam -in:trash';
    }
    pageToken = connection.fetchPageToken || undefined;
  }

  console.log(`Fetching emails: mode=${mode}, query="${query}", pageToken=${pageToken}`);

  // Fetch emails in batches (Gmail API max = 100 per call)
  while (totalFetched < limit) {
    const batchSize = Math.min(100, limit - totalFetched);
    
    try {
      const response = await gmail.users.messages.list({
        userId: 'me',
        maxResults: batchSize,
        pageToken,
        q: query
      });

      if (!response.data.messages || response.data.messages.length === 0) {
        break; // No more emails
      }

      // Get metadata for each email in batch
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

      totalFetched += response.data.messages.length;
      pageToken = response.data.nextPageToken || undefined;
      hasMoreEmails = !!pageToken;

      // Break if we have enough emails or no more pages
      if (!pageToken || totalFetched >= limit) {
        break;
      }

    } catch (error) {
      console.error('Failed to fetch email batch:', error);
      throw error;
    }
  }

  // Store metadata in database
  const storageResult = await storeEmailMetadata(emailMetadata, connection.id);

  // Update connection with pagination state
  await db.update(connections)
    .set({
      lastSyncAt: mode === 'recent' ? new Date() : connection.lastSyncAt,
      fetchPageToken: pageToken,
      oldestFetchedMessageId: mode === 'older' && emailMetadata.length > 0 
        ? emailMetadata[emailMetadata.length - 1].gmailMessageId 
        : connection.oldestFetchedMessageId,
      updatedAt: new Date()
    })
    .where(eq(connections.id, connection.id));

  return {
    emailsFetched: emailMetadata.length,
    newEmails: storageResult.newEmails,
    duplicates: storageResult.duplicates,
    newEmailIds: storageResult.newEmailIds,
    hasMoreEmails
  };
}

async function storeEmailMetadata(emailMetadata: any[], connectionId: string) {
  let newEmails = 0;
  let duplicates = 0;
  const newEmailIds: string[] = [];

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

      // Insert new email metadata and get the ID
      const inserted = await db.insert(processedEmails).values({
        connectionId,
        gmailMessageId: email.gmailMessageId,
        gmailThreadId: email.gmailThreadId,
        subject: email.subject,
        sender: email.sender,
        receivedAt: email.receivedAt,
        fetchedAt: new Date(),
        // Initial state: not yet processed
        isSubscription: false,
        subscriptionId: null,
        confidenceScore: null,
        processingError: null,
        // Phase 2B: Email body storage (will be added during classification)
        emailBody: null,
        bodyStoredAt: null
      }).returning({ id: processedEmails.id });

      if (inserted.length > 0) {
        newEmailIds.push(inserted[0].id);
        newEmails++;
      }

    } catch (error) {
      console.error(`Failed to store email ${email.gmailMessageId}:`, error);
      // Continue processing other emails
    }
  }

  return { newEmails, duplicates, newEmailIds };
}

async function classifyEmails(
  emails: any[],
  gmailService: GmailService,
  classificationService: ClassificationService
) {
  let processed = 0;
  let subscriptionsFound = 0;
  let errors = 0;

  for (const email of emails) {
    try {
      // Fetch full email content from Gmail
      console.log(`Fetching content for email ${email.gmailMessageId}`);
      const emailContent = await gmailService.getMessage(email.gmailMessageId);

      // Classify with LLM
      console.log(`Classifying email: ${email.subject}`);
      const classification = await classificationService.classifyEmail({
        subject: email.subject,
        sender: email.sender,
        body: emailContent.body,
        receivedAt: email.receivedAt
      });

      // Prepare update data
      const updateData: any = {
        isSubscription: classification.isSubscription,
        vendor: classification.vendor,
        emailType: classification.emailType,
        confidenceScore: classification.confidence.toString(),
        classifiedAt: new Date()
      };

      // Phase 2B: Store email body only for subscriptions
      if (classification.isSubscription) {
        updateData.emailBody = emailContent.body;
        updateData.bodyStoredAt = new Date();
      }

      // Update database with classification results
      await db.update(processedEmails)
        .set(updateData)
        .where(eq(processedEmails.id, email.id));

      processed++;
      if (classification.isSubscription) {
        subscriptionsFound++;
      }

      // Reduced delay for faster processing (MVP optimization)
      await new Promise(resolve => setTimeout(resolve, 50));

    } catch (error) {
      console.error(`Failed to classify email ${email.id}:`, error);
      errors++;
      
      // Log error in database
      await db.update(processedEmails)
        .set({
          processingError: error instanceof Error ? error.message : 'Classification failed'
        })
        .where(eq(processedEmails.id, email.id));
    }
  }

  return {
    processed,
    subscriptionsFound,
    errors
  };
}

async function getOldestEmailDate(connectionId: string): Promise<Date | null> {
  try {
    const oldestEmail = await db
      .select({ receivedAt: processedEmails.receivedAt })
      .from(processedEmails)
      .where(eq(processedEmails.connectionId, connectionId))
      .orderBy(asc(processedEmails.receivedAt))
      .limit(1);
    
    return oldestEmail.length > 0 ? oldestEmail[0].receivedAt : null;
  } catch (error) {
    console.error('Failed to get oldest email date:', error);
    return null;
  }
}

function getHeader(headers: gmail_v1.Schema$MessagePartHeader[], name: string): string | undefined {
  return headers.find(h => h.name?.toLowerCase() === name.toLowerCase())?.value || undefined;
}