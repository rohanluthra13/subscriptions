import { EventEmitter } from 'events';

export interface SSEMessage {
  data: any;
  event?: string;
  id?: string;
  retry?: number;
}

export class SSEStream {
  private encoder = new TextEncoder();
  private stream: TransformStream<SSEMessage, Uint8Array>;
  private writer: WritableStreamDefaultWriter<SSEMessage>;
  
  constructor() {
    this.stream = new TransformStream({
      transform: (message, controller) => {
        const lines: string[] = [];
        
        if (message.event) {
          lines.push(`event: ${message.event}`);
        }
        
        if (message.id) {
          lines.push(`id: ${message.id}`);
        }
        
        if (message.retry) {
          lines.push(`retry: ${message.retry}`);
        }
        
        const data = typeof message.data === 'string' 
          ? message.data 
          : JSON.stringify(message.data);
        
        lines.push(`data: ${data}`);
        lines.push(''); // Empty line to end the message
        
        controller.enqueue(this.encoder.encode(lines.join('\n') + '\n'));
      },
    });
    
    this.writer = this.stream.writable.getWriter();
  }
  
  get readable(): ReadableStream<Uint8Array> {
    return this.stream.readable;
  }
  
  async send(data: any, event?: string): Promise<void> {
    await this.writer.write({ data, event });
  }
  
  async close(): Promise<void> {
    await this.writer.close();
  }
}

// Global event emitter for job progress updates
export const jobProgressEmitter = new EventEmitter();

export function createJobProgressStream(jobId: string): ReadableStream<Uint8Array> {
  const sseStream = new SSEStream();
  
  const progressHandler = async (progress: any) => {
    await sseStream.send(progress, 'progress');
  };
  
  const completeHandler = async (result: any) => {
    await sseStream.send(result, 'complete');
    cleanup();
    await sseStream.close();
  };
  
  const errorHandler = async (error: any) => {
    await sseStream.send({ error: error.message }, 'error');
    cleanup();
    await sseStream.close();
  };
  
  const cleanup = () => {
    jobProgressEmitter.off(`progress:${jobId}`, progressHandler);
    jobProgressEmitter.off(`complete:${jobId}`, completeHandler);
    jobProgressEmitter.off(`error:${jobId}`, errorHandler);
  };
  
  // Set up listeners
  jobProgressEmitter.on(`progress:${jobId}`, progressHandler);
  jobProgressEmitter.on(`complete:${jobId}`, completeHandler);
  jobProgressEmitter.on(`error:${jobId}`, errorHandler);
  
  // Send initial connection message
  sseStream.send({ connected: true, jobId }, 'connected');
  
  return sseStream.readable;
}