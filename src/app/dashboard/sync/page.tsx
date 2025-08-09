import { Phase1EmailMetadata } from '@/components/dashboard/phase1-email-metadata';

export default function SyncPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Phase 1: Email Sync</h2>
        <p className="text-gray-600">Fetch and view email metadata from Gmail</p>
      </div>
      
      <Phase1EmailMetadata />
    </div>
  );
}