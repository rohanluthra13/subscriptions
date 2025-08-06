import { NextResponse } from 'next/server';
import { SuccessResponse } from '../types/responses';

export function successResponse<T>(
  data: T,
  message?: string,
  status: number = 200
): NextResponse<SuccessResponse<T>> {
  return NextResponse.json(
    {
      data,
      ...(message && { message }),
    },
    { status }
  );
}

export function createdResponse<T>(
  data: T,
  message: string = 'Created successfully'
): NextResponse<SuccessResponse<T>> {
  return successResponse(data, message, 201);
}

export function noContentResponse(): NextResponse {
  return new NextResponse(null, { status: 204 });
}

export function streamResponse(
  stream: ReadableStream,
  filename: string,
  contentType: string
): NextResponse {
  return new NextResponse(stream, {
    headers: {
      'Content-Type': contentType,
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Cache-Control': 'no-cache',
    },
  });
}

export function sseResponse(stream: ReadableStream): NextResponse {
  return new NextResponse(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}