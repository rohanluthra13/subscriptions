import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { eq, and, isNull, or, sql } from 'drizzle-orm';
import { db } from '@/lib/db';
import { connections, processedEmails, syncJobs } from '@/lib/db/schema';
import { GmailService } from '@/lib/gmail/service';
import { ClassificationService } from '@/lib/llm/classification';

// Phase 2: Email Classification
// Fetches full email content and classifies using LLM

const phase2Schema = z.object({
  limit: z.number().min(1).max(100).default(30),
  emailIds: z.array(z.string()).optional(),
  connectionId: z.string().optional()
});

interface Phase2Request {
  limit?: number;
  emailIds?: string[];
  connectionId?: string;
}

interface Phase2Response {
  success: boolean;
  emailsProcessed: number;
  subscriptionsFound: number;
  errors: number;
  processingTimeMs: number;
  message: string;
  classifications?: Array<{
    emailId: string;
    subject: string;
    isSubscription: boolean;
    vendor?: string;
    emailType?: string;
    confidence?: number;
  }>;
}

export async function POST(request: NextRequest) {
  const startTime = Date.now();
  
  try {
    // Parse request body
    const body: Phase2Request = await request.json();
    const { limit, emailIds, connectionId } = phase2Schema.parse(body);

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

    // Get emails to process
    let emailsToProcess;
    if (emailIds && emailIds.length > 0) {
      // Process specific emails
      emailsToProcess = await db
        .select()
        .from(processedEmails)
        .where(and(
          eq(processedEmails.connectionId, connection.id),
          sql`${processedEmails.id} = ANY(${emailIds})`
        ))
        .limit(limit);
    } else {
      // Get unclassified emails (no vendor means not classified)
      emailsToProcess = await db
        .select()
        .from(processedEmails)
        .where(and(
          eq(processedEmails.connectionId, connection.id),
          isNull(processedEmails.vendor)
        ))
        .limit(limit);
    }

    if (emailsToProcess.length === 0) {
      return NextResponse.json({
        success: true,
        emailsProcessed: 0,
        subscriptionsFound: 0,
        errors: 0,
        processingTimeMs: Date.now() - startTime,
        message: 'No emails to process'
      });
    }

    console.log(`Phase 2: Processing ${emailsToProcess.length} emails for classification`);

    // Initialize services
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

    // Process emails
    const results = await classifyEmails(
      emailsToProcess,
      gmailService,
      classificationService
    );

    // Log sync job for audit trail
    await db.insert(syncJobs).values({
      connectionId: connection.id,
      jobType: 'classification',
      status: 'completed',
      totalEmails: emailsToProcess.length,
      processedEmails: results.processed,
      subscriptionsFound: results.subscriptionsFound,
      errorsCount: results.errors,
      startedAt: new Date(startTime),
      completedAt: new Date()
    });

    const response: Phase2Response = {
      success: true,
      emailsProcessed: results.processed,
      subscriptionsFound: results.subscriptionsFound,
      errors: results.errors,
      processingTimeMs: Date.now() - startTime,
      message: `Phase 2 complete: ${results.processed} emails classified, ${results.subscriptionsFound} subscriptions found`,
      classifications: results.classifications
    };

    console.log('Phase 2 complete:', response);
    return NextResponse.json(response);

  } catch (error) {
    console.error('Phase 2 failed:', error);
    return NextResponse.json(
      { 
        error: 'Phase 2 failed', 
        details: error instanceof Error ? error.message : 'Unknown error',
        processingTimeMs: Date.now() - startTime
      },
      { status: 500 }
    );
  }
}

async function classifyEmails(
  emails: any[],
  gmailService: GmailService,
  classificationService: ClassificationService
) {
  let processed = 0;
  let subscriptionsFound = 0;
  let errors = 0;
  const classifications = [];

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

      // Update database with classification results
      await db.update(processedEmails)
        .set({
          isSubscription: classification.isSubscription,
          vendor: classification.vendor,
          emailType: classification.emailType,
          confidenceScore: classification.confidence.toString(),
          classifiedAt: new Date()
        })
        .where(eq(processedEmails.id, email.id));

      processed++;
      if (classification.isSubscription) {
        subscriptionsFound++;
      }

      classifications.push({
        emailId: email.id,
        subject: email.subject,
        isSubscription: classification.isSubscription,
        vendor: classification.vendor || undefined,
        emailType: classification.emailType || undefined,
        confidence: classification.confidence
      });

      // Small delay to avoid rate limiting
      await new Promise(resolve => setTimeout(resolve, 100));

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
    errors,
    classifications
  };
}

// GET endpoint to retrieve classification results
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = parseInt(searchParams.get('limit') || '10');
  const offset = parseInt(searchParams.get('offset') || '0');
  const onlyClassified = searchParams.get('classified') === 'true';

  try {
    // Build query conditions
    const conditions = [];
    if (onlyClassified) {
      conditions.push(sql`${processedEmails.vendor} IS NOT NULL`);
    }

    // Get total count
    const [{ count }] = await db
      .select({ count: sql<number>`count(*)` })
      .from(processedEmails)
      .where(conditions.length > 0 ? and(...conditions) : undefined);

    // Get emails with pagination
    const emails = await db
      .select({
        id: processedEmails.id,
        gmailMessageId: processedEmails.gmailMessageId,
        subject: processedEmails.subject,
        sender: processedEmails.sender,
        receivedAt: processedEmails.receivedAt,
        fetchedAt: processedEmails.fetchedAt,
        isSubscription: processedEmails.isSubscription,
        vendor: processedEmails.vendor,
        emailType: processedEmails.emailType,
        confidenceScore: processedEmails.confidenceScore,
        classifiedAt: processedEmails.classifiedAt
      })
      .from(processedEmails)
      .where(conditions.length > 0 ? and(...conditions) : undefined)
      .orderBy(sql`${processedEmails.classifiedAt} DESC NULLS LAST, ${processedEmails.fetchedAt} DESC`)
      .limit(limit)
      .offset(offset);

    return NextResponse.json({
      emails,
      total: count,
      limit,
      offset
    });

  } catch (error) {
    console.error('Failed to get classified emails:', error);
    return NextResponse.json(
      { error: 'Failed to retrieve classified emails' },
      { status: 500 }
    );
  }
}