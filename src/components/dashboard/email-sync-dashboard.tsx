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
  isSubscription?: boolean;
  vendor?: string;
  emailType?: string;
  confidenceScore?: number;
  classifiedAt?: string;
}

interface SyncResponse {
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

export function EmailSyncDashboard() {
  const [isRunningSync, setIsRunningSync] = useState(false);
  const [syncResult, setSyncResult] = useState<SyncResponse | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [emailLimit, setEmailLimit] = useState(30);
  const [showClassified, setShowClassified] = useState(false);
  const [syncProgress, setSyncProgress] = useState<{ current: number; total: number } | null>(null);
  
  const pageSize = 10;
  
  const { data: emailsData, error: emailsError, isLoading: emailsLoading, mutate: refreshEmails } = useSWR(
    showClassified 
      ? `/api/sync/phase2?classified=true&limit=${pageSize}&offset=${currentPage * pageSize}`
      : `/api/sync/phase1/emails?limit=${pageSize}&offset=${currentPage * pageSize}`,
    fetcher
  );

  const { data: connectionData } = useSWR('/api/connections/status', fetcher);

  const handleSync = async (mode: 'recent' | 'older') => {
    setIsRunningSync(true);
    setSyncResult(null);
    setSyncProgress(null);
    
    try {
      const response = await fetch('/api/sync/emails', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || 'dev-key-123'
        },
        body: JSON.stringify({ 
          mode,
          limit: emailLimit,
          autoClassify: true
        })
      });
      
      const result = await response.json();
      
      if (response.ok) {
        setSyncResult(result);
        refreshEmails();
      } else {
        setSyncResult({
          success: false,
          phase1: { emailsFetched: 0, newEmails: 0, duplicates: 0 },
          phase2: { emailsProcessed: 0, subscriptionsFound: 0, errors: 0 },
          processingTimeMs: 0,
          hasMoreEmails: false,
          message: result.error || 'Sync failed'
        });
      }
    } catch (error) {
      console.error('Sync failed:', error);
      setSyncResult({
        success: false,
        phase1: { emailsFetched: 0, newEmails: 0, duplicates: 0 },
        phase2: { emailsProcessed: 0, subscriptionsFound: 0, errors: 0 },
        processingTimeMs: 0,
        hasMoreEmails: false,
        message: 'Network error during sync'
      });
    } finally {
      setIsRunningSync(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatTimeAgo = (dateString: string) => {
    const now = new Date();
    const date = new Date(dateString);
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    
    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  const truncateText = (text: string, maxLength: number = 50) => {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  const totalPages = emailsData ? Math.ceil(emailsData.total / pageSize) : 0;
  const connection = connectionData?.connections?.[0];

  return (
    <div className="space-y-6">
      {/* Unified Sync Controls */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Email Sync & Classification</h3>
            <p className="text-sm text-gray-600">
              Fetch and classify emails in one unified process
            </p>
          </div>
        </div>

        {/* Status Display */}
        <div className="flex items-center justify-between mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex items-center space-x-6">
            <div>
              <span className="text-sm font-medium text-gray-700">Status:</span>
              <span className="ml-2 text-sm text-gray-900">
                {isRunningSync ? 'Processing...' : 'Ready'}
              </span>
            </div>
            {connection?.lastSyncAt && (
              <div>
                <span className="text-sm font-medium text-gray-700">Last sync:</span>
                <span className="ml-2 text-sm text-gray-900">
                  {formatTimeAgo(connection.lastSyncAt)}
                </span>
              </div>
            )}
          </div>
          {emailsData && (
            <div className="text-right">
              <span className="text-sm font-medium text-gray-700">Total processed:</span>
              <span className="ml-2 text-sm text-gray-900">
                {emailsData.total} emails
              </span>
            </div>
          )}
        </div>

        {/* Sync Controls */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-4">
            <Button
              onClick={() => handleSync('recent')}
              disabled={isRunningSync}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {isRunningSync ? 'Syncing...' : 'Sync Recent Emails'}
            </Button>
            <Button
              onClick={() => handleSync('older')}
              disabled={isRunningSync}
              variant="outline"
            >
              Fetch Older
            </Button>
          </div>
          <div className="flex items-center space-x-4">
            <label className="text-sm font-medium text-gray-700">Batch size:</label>
            <select
              value={emailLimit}
              onChange={(e) => setEmailLimit(Number(e.target.value))}
              className="px-3 py-1 border border-gray-300 rounded-md text-sm"
              disabled={isRunningSync}
            >
              <option value={5}>5 emails</option>
              <option value={30}>30 emails</option>
              <option value={100}>100 emails</option>
              <option value={500}>500 emails</option>
            </select>
          </div>
        </div>

        {/* Progress Indicator */}
        {isRunningSync && (
          <div className="mb-6 p-4 bg-blue-50 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-blue-700">Processing emails...</span>
              {syncProgress && (
                <span className="text-sm text-blue-600">
                  {syncProgress.current} of {syncProgress.total}
                </span>
              )}
            </div>
            <div className="w-full bg-blue-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ 
                  width: syncProgress 
                    ? `${(syncProgress.current / syncProgress.total) * 100}%` 
                    : '0%' 
                }}
              ></div>
            </div>
          </div>
        )}

        {/* Sync Results */}
        {syncResult && (
          <div className={`p-4 rounded-md ${syncResult.success ? 'bg-green-50' : 'bg-red-50'}`}>
            <div className="flex items-center justify-between">
              <div>
                <Badge className={syncResult.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}>
                  {syncResult.success ? 'Success' : 'Failed'}
                </Badge>
                <p className="text-sm mt-1">{syncResult.message}</p>
              </div>
              {syncResult.success && (
                <div className="text-right text-sm text-gray-600 space-y-1">
                  <div>📥 Fetched: {syncResult.phase1.emailsFetched} emails</div>
                  <div>🆕 New: {syncResult.phase1.newEmails}</div>
                  <div>📧 Subscriptions found: {syncResult.phase2.subscriptionsFound}</div>
                  <div>⏱️ Time: {Math.round(syncResult.processingTimeMs / 1000)}s</div>
                  {syncResult.hasMoreEmails && (
                    <div className="text-blue-600">📚 More emails available</div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </Card>

      {/* Email Data Table */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-4">
            <h3 className="text-lg font-semibold text-gray-900">Email Data</h3>
            <div className="flex space-x-2">
              <Button
                variant={!showClassified ? "default" : "outline"}
                size="sm"
                onClick={() => { setShowClassified(false); setCurrentPage(0); }}
              >
                All Emails
              </Button>
              <Button
                variant={showClassified ? "default" : "outline"}
                size="sm"
                onClick={() => { setShowClassified(true); setCurrentPage(0); }}
              >
                Classified
              </Button>
            </div>
          </div>
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
            Failed to load email data. Please try again.
          </div>
        ) : emailsData?.emails.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            <p>No emails found.</p>
            <p className="text-sm mt-1">Click &quot;Sync Recent Emails&quot; to get started.</p>
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-gray-900 font-semibold">Subject</TableHead>
                  <TableHead className="text-gray-900 font-semibold">Sender</TableHead>
                  {showClassified && (
                    <>
                      <TableHead className="text-gray-900 font-semibold">Subscription</TableHead>
                      <TableHead className="text-gray-900 font-semibold">Vendor</TableHead>
                      <TableHead className="text-gray-900 font-semibold">Type</TableHead>
                    </>
                  )}
                  <TableHead className="text-gray-900 font-semibold">
                    {showClassified ? 'Classified' : 'Received'}
                  </TableHead>
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
                    {showClassified && (
                      <>
                        <TableCell>
                          {email.isSubscription ? (
                            <Badge className="bg-green-100 text-green-800 text-xs">
                              Yes
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-gray-600 text-xs">
                              No
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          {email.vendor ? (
                            <Badge variant="outline" className="text-xs">
                              {email.vendor}
                            </Badge>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {email.emailType ? (
                            <span className="text-sm text-gray-600">{email.emailType}</span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </TableCell>
                      </>
                    )}
                    <TableCell className="text-sm text-gray-600">
                      {formatDate(showClassified && email.classifiedAt ? email.classifiedAt : email.receivedAt)}
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