import { SyncStatus } from '@/components/dashboard/sync-status';

export default function SyncPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Sync Status</h2>
        <p className="text-gray-600">Monitor email processing and trigger manual syncs</p>
      </div>
      
      <SyncStatus />
    </div>
  );
}