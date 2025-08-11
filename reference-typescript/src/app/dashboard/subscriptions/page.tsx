import { SubscriptionTable } from '@/components/dashboard/subscription-table';

export default function SubscriptionsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Subscriptions</h2>
        <p className="text-gray-600">Manage your detected subscriptions</p>
      </div>
      
      <SubscriptionTable />
    </div>
  );
}