import { createApiHandler } from '@/lib/api/middleware';
import { successResponse } from '@/lib/api/utils/response';
import { DatabaseService } from '@/lib/db/service';

export const GET = createApiHandler(async () => {
  const database = new DatabaseService();
  const connection = await database.getActiveConnection('1');
  
  return successResponse({
    connection: connection ? {
      id: connection.id,
      email: connection.email,
      is_active: connection.isActive,
      last_sync_at: connection.lastSyncAt?.toISOString(),
      created_at: connection.createdAt?.toISOString(),
    } : null,
  });
});