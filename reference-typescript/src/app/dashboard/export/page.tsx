import { Card } from '@/components/ui/card';
import { ExportButton } from '@/components/dashboard/export-button';

export default function ExportPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Export Data</h2>
        <p className="text-gray-600">Download your subscription data in various formats</p>
      </div>
      
      <Card className="p-6">
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Export Options</h3>
            <p className="text-gray-600 text-sm mb-4">
              Export all your subscription data or apply filters before downloading.
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <h4 className="font-medium text-gray-900">Quick Export</h4>
              <div className="space-y-2">
                <ExportButton />
                <p className="text-xs text-gray-500">
                  Exports all subscriptions
                </p>
              </div>
            </div>
            
            <div className="space-y-3">
              <h4 className="font-medium text-gray-900">Active Only</h4>
              <div className="space-y-2">
                <ExportButton filters={{ status: 'active' }} />
                <p className="text-xs text-gray-500">
                  Exports only active subscriptions
                </p>
              </div>
            </div>
          </div>
          
          <div className="pt-4 border-t border-gray-200">
            <h4 className="font-medium text-gray-900 mb-2">Export Formats</h4>
            <div className="space-y-2 text-sm text-gray-600">
              <div>📊 <strong>CSV:</strong> Open in Excel, Google Sheets, or other spreadsheet apps</div>
              <div>📄 <strong>JSON:</strong> Machine-readable format for developers and integrations</div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}