export interface PaginationParams {
  limit: number;
  offset: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
}

export function createPaginatedResponse<T>(
  items: T[],
  total: number,
  params: PaginationParams
): PaginatedResponse<T> {
  const { limit, offset } = params;
  
  return {
    items,
    total,
    limit,
    offset,
    hasMore: offset + items.length < total,
  };
}

export function calculateTotalPages(total: number, limit: number): number {
  return Math.ceil(total / limit);
}

export function validatePaginationParams(params: PaginationParams): void {
  if (params.limit < 1 || params.limit > 100) {
    throw new Error('Limit must be between 1 and 100');
  }
  
  if (params.offset < 0) {
    throw new Error('Offset must be non-negative');
  }
}