import { NextRequest, NextResponse } from 'next/server';
import { db } from '@/lib/db';
import { processedEmails } from '@/lib/db/schema';
import { and, eq, isNotNull, sql, desc, isNull } from 'drizzle-orm';

// GET endpoint to retrieve processed emails
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = parseInt(searchParams.get('limit') || '10');
  const offset = parseInt(searchParams.get('offset') || '0');
  const classified = searchParams.get('classified') === 'true';

  try {
    // Build query conditions
    const conditions = [];
    if (classified) {
      conditions.push(isNotNull(processedEmails.classifiedAt));
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
      .orderBy(desc(processedEmails.fetchedAt))
      .limit(limit)
      .offset(offset);

    return NextResponse.json({
      emails,
      total: count,
      limit,
      offset
    });

  } catch (error) {
    console.error('Failed to get emails:', error);
    return NextResponse.json(
      { error: 'Failed to retrieve emails' },
      { status: 500 }
    );
  }
}