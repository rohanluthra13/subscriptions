'use client';

import { Button } from '@/components/ui/button';
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
  amount: string;
  currency: string;
}

interface DeleteSubscriptionDialogProps {
  subscription: Subscription | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (id: string) => Promise<void>;
  isDeleting: boolean;
}

export function DeleteSubscriptionDialog({
  subscription,
  open,
  onOpenChange,
  onConfirm,
  isDeleting,
}: DeleteSubscriptionDialogProps) {
  const handleConfirm = async () => {
    if (!subscription) return;
    await onConfirm(subscription.id);
    onOpenChange(false);
  };

  if (!subscription) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Delete Subscription</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete this subscription? This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        
        <div className="py-4">
          <div className="bg-gray-50 rounded-md p-4">
            <div className="font-medium text-gray-900">{subscription.vendorName}</div>
            <div className="text-sm text-gray-600">
              {parseFloat(subscription.amount || '0') > 0 
                ? `${subscription.currency}${parseFloat(subscription.amount).toFixed(2)}`
                : 'Unknown amount'
              }
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button 
            variant="destructive" 
            onClick={handleConfirm}
            disabled={isDeleting}
          >
            {isDeleting ? 'Deleting...' : 'Delete Subscription'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}