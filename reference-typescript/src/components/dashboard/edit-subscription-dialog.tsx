'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface Subscription {
  id: string;
  vendorName: string;
  vendorEmail: string;
  amount: string;
  currency: string;
  billingCycle: string;
  nextBillingDate: string | null;
  status: string;
  category: string;
  userNotes?: string;
}

interface EditSubscriptionDialogProps {
  subscription: Subscription | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (id: string, data: Partial<Subscription>) => Promise<void>;
}

export function EditSubscriptionDialog({
  subscription,
  open,
  onOpenChange,
  onSave,
}: EditSubscriptionDialogProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    amount: '',
    status: '',
    userNotes: '',
  });

  const handleSave = async () => {
    if (!subscription) return;
    
    setIsLoading(true);
    try {
      await onSave(subscription.id, {
        amount: formData.amount || subscription.amount,
        status: formData.status || subscription.status,
        userNotes: formData.userNotes,
      });
      onOpenChange(false);
    } catch (error) {
      console.error('Failed to save subscription:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (!subscription) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Edit Subscription</DialogTitle>
          <DialogDescription>
            Update details for {subscription.vendorName}
          </DialogDescription>
        </DialogHeader>
        
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium text-gray-700">Vendor</label>
            <div className="mt-1 text-sm text-gray-900">{subscription.vendorName}</div>
            <div className="text-xs text-gray-500">{subscription.vendorEmail}</div>
          </div>
          
          <div>
            <label className="text-sm font-medium text-gray-700">Amount</label>
            <Input
              type="number"
              step="0.01"
              placeholder={subscription.amount}
              value={formData.amount}
              onChange={(e) => setFormData(prev => ({ ...prev, amount: e.target.value }))}
            />
          </div>
          
          <div>
            <label className="text-sm font-medium text-gray-700">Status</label>
            <select
              className="mt-1 block w-full rounded-md border-gray-300 text-sm"
              value={formData.status || subscription.status}
              onChange={(e) => setFormData(prev => ({ ...prev, status: e.target.value }))}
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="paused">Paused</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>
          
          <div>
            <label className="text-sm font-medium text-gray-700">Notes</label>
            <Input
              placeholder="Add personal notes..."
              value={formData.userNotes}
              onChange={(e) => setFormData(prev => ({ ...prev, userNotes: e.target.value }))}
            />
          </div>
          
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Billing Cycle:</span>
              <Badge variant="outline" className="ml-2">{subscription.billingCycle}</Badge>
            </div>
            <div>
              <span className="text-gray-500">Category:</span>
              <Badge variant="outline" className="ml-2">{subscription.category}</Badge>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isLoading}>
            {isLoading ? 'Saving...' : 'Save Changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}