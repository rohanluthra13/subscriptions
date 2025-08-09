import { Suspense } from 'react';
import { Card } from '@/components/ui/card';
import { GmailConnection } from '@/components/dashboard/gmail-connection';
import { Phase1EmailMetadata } from '@/components/dashboard/phase1-email-metadata';

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Mechanics</h2>
        <p className="text-gray-600">Email processing pipeline testing</p>
      </div>
      
      <Suspense fallback={<Card className="p-6"><div className="animate-pulse"><div className="h-4 bg-gray-200 rounded w-1/4 mb-2"></div><div className="h-4 bg-gray-200 rounded w-1/2"></div></div></Card>}>
        <GmailConnection />
      </Suspense>
      
      <Phase1EmailMetadata />
    </div>
  );
}