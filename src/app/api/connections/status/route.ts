import { createApiHandler } from '@/lib/api/middleware';
import { successResponse } from '@/lib/api/utils/response';
import { DatabaseService } from '@/lib/db/service';

export const GET = createApiHandler(async () => {
  const database = new DatabaseService();
  
  console.log('Checking connection for userId: 1');
  const connection = await database.getActiveConnection('1');
  console.log('Found connection:', connection ? {
    id: connection.id,
    email: connection.email,
    isActive: connection.isActive
  } : 'null');
  
  const responseData = {
    connection: connection ? {
      id: connection.id,
      email: connection.email,
      is_active: connection.isActive,
      last_sync_at: connection.lastSyncAt?.toISOString(),
      created_at: connection.createdAt?.toISOString(),
    } : null,
  };
  
  console.log('Returning connection data:', responseData);
  
  return successResponse(responseData);
});