import { Subscription } from '@/lib/db/schema';

export function generateCSV(subscriptions: Subscription[]): string {
  const headers = [
    'ID',
    'Vendor Name',
    'Vendor Email',
    'Amount',
    'Currency',
    'Billing Cycle',
    'Status',
    'Renewal Type',
    'Next Billing Date',
    'Last Billing Date',
    'Category',
    'Confidence Score',
    'User Verified',
    'User Notes',
    'Detected At',
  ];
  
  const rows = subscriptions.map(sub => [
    sub.id,
    escapeCSVField(sub.vendorName),
    escapeCSVField(sub.vendorEmail || ''),
    sub.amount || '',
    sub.currency || '',
    sub.billingCycle || '',
    sub.status || '',
    sub.renewalType || '',
    sub.nextBillingDate || '',
    sub.lastBillingDate || '',
    sub.category || '',
    sub.confidenceScore || '',
    sub.userVerified ? 'true' : 'false',
    escapeCSVField(sub.userNotes || ''),
    sub.detectedAt?.toISOString() || '',
  ]);
  
  const csvContent = [headers, ...rows]
    .map(row => row.join(','))
    .join('\n');
  
  return csvContent;
}

export function escapeCSVField(field: string): string {
  if (field.includes(',') || field.includes('"') || field.includes('\n')) {
    return `"${field.replace(/"/g, '""')}"`;
  }
  return field;
}

export function createCSVStream(subscriptions: Subscription[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  
  return new ReadableStream({
    start(controller) {
      // Send CSV header
      const headers = [
        'ID',
        'Vendor Name',
        'Vendor Email',
        'Amount',
        'Currency',
        'Billing Cycle',
        'Status',
        'Renewal Type',
        'Next Billing Date',
        'Last Billing Date',
        'Category',
        'Confidence Score',
        'User Verified',
        'User Notes',
        'Detected At',
      ];
      
      controller.enqueue(encoder.encode(headers.join(',') + '\n'));
    },
    
    pull(controller) {
      // Send each subscription as a CSV row
      for (const subscription of subscriptions) {
        const row = [
          subscription.id,
          escapeCSVField(subscription.vendorName),
          escapeCSVField(subscription.vendorEmail || ''),
          subscription.amount || '',
          subscription.currency || '',
          subscription.billingCycle || '',
          subscription.status || '',
          subscription.renewalType || '',
          subscription.nextBillingDate || '',
          subscription.lastBillingDate || '',
          subscription.category || '',
          subscription.confidenceScore || '',
          subscription.userVerified ? 'true' : 'false',
          escapeCSVField(subscription.userNotes || ''),
          subscription.detectedAt?.toISOString() || '',
        ];
        
        controller.enqueue(encoder.encode(row.join(',') + '\n'));
      }
      
      controller.close();
    },
  });
}

export function createJSONStream(subscriptions: Subscription[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode('{"subscriptions":['));
    },
    
    pull(controller) {
      subscriptions.forEach((subscription, index) => {
        const comma = index > 0 ? ',' : '';
        const json = JSON.stringify(subscription, null, 2);
        controller.enqueue(encoder.encode(comma + json));
      });
      
      controller.enqueue(encoder.encode(']}'));
      controller.close();
    },
  });
}

export function generateFilename(format: 'csv' | 'json', filters?: Record<string, any>): string {
  const timestamp = new Date().toISOString().split('T')[0];
  const filterSuffix = filters?.status ? `_${filters.status}` : '';
  return `subscriptions_${timestamp}${filterSuffix}.${format}`;
}