'use client';

import { Badge } from '@/components/ui/badge';

export function DashboardHeader() {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h1 className="text-xl font-semibold text-gray-900">
            Subscription Tracker
          </h1>
          <Badge variant="secondary">MVP</Badge>
        </div>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-600">
            Single User Mode
          </span>
        </div>
      </div>
    </header>
  );
}