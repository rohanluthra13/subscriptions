import { Card } from '@/components/ui/card';
import { GmailConnection } from '@/components/dashboard/gmail-connection';

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Overview</h2>
        <p className="text-gray-600">Monitor your subscription spending and activity</p>
      </div>
      
      <GmailConnection />
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="p-6">
          <h3 className="text-sm font-medium text-gray-500">Monthly Total</h3>
          <p className="text-2xl font-bold text-gray-900">$0.00</p>
        </Card>
        
        <Card className="p-6">
          <h3 className="text-sm font-medium text-gray-500">Active Subscriptions</h3>
          <p className="text-2xl font-bold text-gray-900">0</p>
        </Card>
        
        <Card className="p-6">
          <h3 className="text-sm font-medium text-gray-500">Last Sync</h3>
          <p className="text-2xl font-bold text-gray-900">Never</p>
        </Card>
      </div>

      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Getting Started</h3>
        <p className="text-gray-600 mb-4">
          Connect your Gmail account to start tracking subscriptions automatically.
        </p>
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-medium">1</span>
            <span className="text-sm text-gray-600">Connect Gmail account</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-6 h-6 rounded-full bg-gray-100 text-gray-400 flex items-center justify-center text-xs font-medium">2</span>
            <span className="text-sm text-gray-400">Sync your emails (will process last 6 months)</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="w-6 h-6 rounded-full bg-gray-100 text-gray-400 flex items-center justify-center text-xs font-medium">3</span>
            <span className="text-sm text-gray-400">Review and manage your subscriptions</span>
          </div>
        </div>
      </Card>
    </div>
  );
}