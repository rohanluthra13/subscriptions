'use client';

import { useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type ColumnFiltersState,
} from '@tanstack/react-table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useSubscriptions, useDeleteSubscription } from '@/hooks/use-subscriptions';
import { EditSubscriptionDialog } from './edit-subscription-dialog';
import { DeleteSubscriptionDialog } from './delete-subscription-dialog';
import { ExportButton } from './export-button';

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
  detectedAt: string;
}

export function SubscriptionTable() {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [globalFilter, setGlobalFilter] = useState('');
  const [editSubscription, setEditSubscription] = useState<Subscription | null>(null);
  const [deleteSubscription, setDeleteSubscription] = useState<Subscription | null>(null);

  const { subscriptions, total, summary, isLoading, error, refresh } = useSubscriptions({
    search: globalFilter,
    sort: sorting[0]?.id as any,
    order: sorting[0]?.desc ? 'desc' : 'asc',
  });

  const { deleteSubscription: performDelete, isDeleting } = useDeleteSubscription();

  const columns: ColumnDef<Subscription>[] = [
    {
      accessorKey: 'vendorName',
      header: 'Vendor',
      cell: ({ row }) => (
        <div>
          <div className="font-medium">{row.getValue('vendorName')}</div>
          <div className="text-sm text-gray-500">{row.original.vendorEmail}</div>
        </div>
      ),
    },
    {
      accessorKey: 'amount',
      header: 'Amount',
      cell: ({ row }) => {
        const amount = parseFloat(row.getValue('amount') || '0');
        return (
          <div className="font-medium">
            {amount > 0 ? `${row.original.currency}${amount.toFixed(2)}` : 'Unknown'}
          </div>
        );
      },
    },
    {
      accessorKey: 'billingCycle',
      header: 'Cycle',
      cell: ({ row }) => (
        <Badge variant="outline">
          {row.getValue('billingCycle') || 'Unknown'}
        </Badge>
      ),
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => {
        const status = row.getValue('status') as string;
        const variant = status === 'active' ? 'default' : 'secondary';
        return <Badge variant={variant}>{status}</Badge>;
      },
    },
    {
      accessorKey: 'category',
      header: 'Category',
      cell: ({ row }) => (
        <Badge variant="outline">
          {row.getValue('category')}
        </Badge>
      ),
    },
    {
      accessorKey: 'nextBillingDate',
      header: 'Next Billing',
      cell: ({ row }) => {
        const date = row.getValue('nextBillingDate') as string;
        return date ? new Date(date).toLocaleDateString() : 'Unknown';
      },
    },
    {
      id: 'actions',
      cell: ({ row }) => (
        <div className="flex space-x-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setEditSubscription(row.original)}
          >
            Edit
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => setDeleteSubscription(row.original)}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  const table = useReactTable({
    data: subscriptions,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onGlobalFilterChange: setGlobalFilter,
    state: {
      sorting,
      columnFilters,
      globalFilter,
    },
  });

  if (error) {
    return (
      <Card className="p-6 border-red-200">
        <p className="text-red-600">Failed to load subscriptions</p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Subscriptions</h3>
          <p className="text-sm text-gray-600">
            {total} subscription{total !== 1 ? 's' : ''} found
          </p>
        </div>
        
        <div className="flex items-center space-x-4">
          <Input
            placeholder="Search subscriptions..."
            value={globalFilter ?? ''}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="w-64"
          />
          <ExportButton filters={{ search: globalFilter }} />
        </div>
      </div>

      <Card>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  <div className="animate-pulse">Loading subscriptions...</div>
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  No subscriptions found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      <EditSubscriptionDialog
        subscription={editSubscription}
        open={!!editSubscription}
        onOpenChange={(open) => !open && setEditSubscription(null)}
        onSave={async (id, data) => {
          const response = await fetch(`/api/subscriptions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
          });
          if (response.ok) {
            refresh();
          }
        }}
      />

      <DeleteSubscriptionDialog
        subscription={deleteSubscription}
        open={!!deleteSubscription}
        onOpenChange={(open) => !open && setDeleteSubscription(null)}
        onConfirm={async (id) => {
          const success = await performDelete(id);
          if (success) {
            refresh();
          }
        }}
        isDeleting={isDeleting}
      />
    </div>
  );
}