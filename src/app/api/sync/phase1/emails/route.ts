import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { eq, desc } from 'drizzle-orm';
import { db } from '@/lib/db';
import { processedEmails } from '@/lib/db/schema';

// Get Phase 1 stored email metadata for UI display

const emailsQuerySchema = z.object({
  limit: z.string().nullable().optional().transform(val => val ? Number(val) : undefined),
  offset: z.string().nullable().optional().transform(val => val ? Number(val) : undefined),
  connectionId: z.string().nullable().optional()
});

interface EmailMetadataResponse {
  success: boolean;
  emails: Array<{
    id: string;
    gmailMessageId: string;
    subject: string;
    sender: string;
    receivedAt: string;
    fetchedAt: string;
  }>;
  total: number;
  hasMore: boolean;
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const query = emailsQuerySchema.parse({
      limit: searchParams.get('limit'),
      offset: searchParams.get('offset'),
      connectionId: searchParams.get('connectionId')
    });

    const limit = query.limit || 30;
    const offset = query.offset || 0;

    // Build query with optional connection filter
    const whereCondition = query.connectionId 
      ? eq(processedEmails.connectionId, query.connectionId)
      : undefined;

    // Get emails with pagination
    const emails = await db
      .select({
        id: processedEmails.id,
        gmailMessageId: processedEmails.gmailMessageId,
        subject: processedEmails.subject,
        sender: processedEmails.sender,
        receivedAt: processedEmails.receivedAt,
        fetchedAt: processedEmails.fetchedAt
      })
      .from(processedEmails)
      .where(whereCondition)
      .orderBy(desc(processedEmails.receivedAt))
      .limit(limit + 1) // Get one extra to check if there are more
      .offset(offset);

    // Check if there are more emails
    const hasMore = emails.length > limit;
    const emailsToReturn = hasMore ? emails.slice(0, limit) : emails;

    // Get total count (for UI)
    const totalResult = await db
      .select({ count: processedEmails.id })
      .from(processedEmails);
    
    const total = totalResult.length;

    const response: EmailMetadataResponse = {
      success: true,
      emails: emailsToReturn.map(email => ({
        id: email.id,
        gmailMessageId: email.gmailMessageId,
        subject: email.subject || 'No Subject',
        sender: email.sender || 'Unknown Sender',
        receivedAt: email.receivedAt?.toISOString() || new Date().toISOString(),
        fetchedAt: email.fetchedAt?.toISOString() || new Date().toISOString()
      })),
      total,
      hasMore
    };

    return NextResponse.json(response);

  } catch (error) {
    console.error('Failed to fetch email metadata:', error);
    return NextResponse.json(
      { 
        error: 'Failed to fetch email metadata', 
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}