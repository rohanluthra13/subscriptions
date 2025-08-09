'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import useSWR from 'swr';

const fetcher = (url: string) => fetch(url, {
  headers: {
    'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || 'dev-key-123'
  }
}).then(res => res.json());

interface EmailMetadata {
  id: string;
  gmailMessageId: string;
  subject: string;
  sender: string;
  receivedAt: string;
  fetchedAt: string;
}

interface Phase1Response {
  success: boolean;
  emailsFetched: number;
  newEmails: number;
  duplicates: number;
  processingTimeMs: number;
  message: string;
}

export function Phase1EmailMetadata() {
  const [isRunningPhase1, setIsRunningPhase1] = useState(false);
  const [phase1Result, setPhase1Result] = useState<Phase1Response | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [emailLimit, setEmailLimit] = useState(30);
  
  const pageSize = 10;
  
  const { data: emailsData, error: emailsError, isLoading: emailsLoading, mutate: refreshEmails } = useSWR(
    `/api/sync/phase1/emails?limit=${pageSize}&offset=${currentPage * pageSize}`,
    fetcher
  );

  const handleRunPhase1 = async () => {
    setIsRunningPhase1(true);
    setPhase1Result(null);
    
    try {
      const response = await fetch('/api/sync/phase1', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || 'dev-key-123'
        },
        body: JSON.stringify({ limit: emailLimit })
      });
      
      const result = await response.json();
      
      if (response.ok) {
        setPhase1Result(result);
        refreshEmails(); // Refresh the email list
      } else {
        setPhase1Result({
          success: false,
          emailsFetched: 0,
          newEmails: 0,
          duplicates: 0,
          processingTimeMs: 0,
          message: result.error || 'Phase 1 failed'
        });
      }
    } catch (error) {
      console.error('Phase 1 failed:', error);
      setPhase1Result({
        success: false,
        emailsFetched: 0,
        newEmails: 0,
        duplicates: 0,
        processingTimeMs: 0,
        message: 'Network error during Phase 1'
      });
    } finally {
      setIsRunningPhase1(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const truncateText = (text: string, maxLength: number = 50) => {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  const totalPages = emailsData ? Math.ceil(emailsData.total / pageSize) : 0;

  return (
    <div className="space-y-6">
      {/* Phase 1 Controls */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Phase 1: Email Metadata</h3>
            <p className="text-sm text-gray-600">
              Fetch email metadata from Gmail (subjects, senders, dates)
            </p>
          </div>
          <div className="flex items-center space-x-4">
            <select
              value={emailLimit}
              onChange={(e) => setEmailLimit(Number(e.target.value))}
              className="px-3 py-1 border border-gray-300 rounded-md text-sm"
              disabled={isRunningPhase1}
            >
              <option value={5}>5 emails</option>
              <option value={30}>30 emails</option>
              <option value={100}>100 emails</option>
              <option value={500}>500 emails</option>
            </select>
            <Button
              onClick={handleRunPhase1}
              disabled={isRunningPhase1}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {isRunningPhase1 ? 'Fetching...' : 'Run Phase 1'}
            </Button>
          </div>
        </div>

        {/* Phase 1 Results */}
        {phase1Result && (
          <div className={`p-4 rounded-md ${phase1Result.success ? 'bg-green-50' : 'bg-red-50'}`}>
            <div className="flex items-center justify-between">
              <div>
                <Badge className={phase1Result.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                  {phase1Result.success ? 'Success' : 'Failed'}
                </Badge>
                <p className="text-sm mt-1">{phase1Result.message}</p>
              </div>
              {phase1Result.success && (
                <div className="text-right text-sm text-gray-600">
                  <div>Fetched: {phase1Result.emailsFetched}</div>
                  <div>New: {phase1Result.newEmails}</div>
                  <div>Duplicates: {phase1Result.duplicates}</div>
                  <div>Time: {phase1Result.processingTimeMs}ms</div>
                </div>
              )}
            </div>
          </div>
        )}
      </Card>

      {/* Email Metadata Table */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Fetched Email Metadata</h3>
          {emailsData && (
            <span className="text-sm text-gray-600">
              Total: {emailsData.total} emails
            </span>
          )}
        </div>

        {emailsLoading ? (
          <div className="animate-pulse space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-200 rounded"></div>
            ))}
          </div>
        ) : emailsError ? (
          <div className="p-4 bg-red-50 text-red-600 rounded-md text-sm">
            Failed to load email metadata. Please try again.
          </div>
        ) : emailsData?.emails.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p>No email metadata found.</p>
            <p className="text-sm mt-1">Run Phase 1 to fetch emails from Gmail.</p>
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-gray-900 font-semibold">Subject</TableHead>
                  <TableHead className="text-gray-900 font-semibold">Sender</TableHead>
                  <TableHead className="text-gray-900 font-semibold">Received</TableHead>
                  <TableHead className="text-gray-900 font-semibold">Fetched</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {emailsData?.emails.map((email: EmailMetadata) => (
                  <TableRow key={email.id}>
                    <TableCell className="font-medium text-gray-900">
                      {truncateText(email.subject)}
                    </TableCell>
                    <TableCell className="text-gray-800">
                      {truncateText(email.sender, 30)}
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {formatDate(email.receivedAt)}
                    </TableCell>
                    <TableCell className="text-sm text-gray-600">
                      {formatDate(email.fetchedAt)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <div className="text-sm text-gray-600">
                  Page {currentPage + 1} of {totalPages}
                </div>
                <div className="flex space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
                    disabled={currentPage === 0}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
                    disabled={currentPage >= totalPages - 1}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}