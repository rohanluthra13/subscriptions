import { EmailSyncDashboard } from '@/components/dashboard/email-sync-dashboard';

export default function SyncPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Email Sync & Classification</h2>
        <p className="text-gray-600">Unified email fetching and classification pipeline</p>
      </div>
      
      <EmailSyncDashboard />
    </div>
  );
}