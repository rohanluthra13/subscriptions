import crypto from 'crypto';

/**
 * Token encryption utilities for storing OAuth tokens securely
 * Uses AES-256-CBC as specified in DESIGN.md
 */

const ALGORITHM = 'aes-256-cbc';
const IV_LENGTH = 16; // AES block size

/**
 * Encrypts a token for secure storage
 * @param token - Plain text token to encrypt
 * @returns Encrypted token with IV prepended
 */
export function encryptToken(token: string): string {
  const encryptionKey = process.env.ENCRYPTION_KEY;
  if (!encryptionKey) {
    throw new Error('ENCRYPTION_KEY environment variable is not set');
  }

  // Generate a random initialization vector
  const iv = crypto.randomBytes(IV_LENGTH);
  
  // Create cipher with key and IV
  const cipher = crypto.createCipheriv(
    ALGORITHM,
    Buffer.from(encryptionKey, 'hex'), // 32-byte hex string
    iv
  );

  // Encrypt the token
  let encrypted = cipher.update(token, 'utf8', 'hex');
  encrypted += cipher.final('hex');

  // Prepend IV to encrypted data for storage
  return iv.toString('hex') + ':' + encrypted;
}

/**
 * Decrypts a token for use
 * @param encryptedToken - Encrypted token with IV prepended
 * @returns Plain text token
 */
export function decryptToken(encryptedToken: string): string {
  const encryptionKey = process.env.ENCRYPTION_KEY;
  if (!encryptionKey) {
    throw new Error('ENCRYPTION_KEY environment variable is not set');
  }

  // Split IV and encrypted data
  const parts = encryptedToken.split(':');
  if (parts.length !== 2) {
    throw new Error('Invalid encrypted token format');
  }

  const iv = Buffer.from(parts[0], 'hex');
  const encrypted = parts[1];

  // Create decipher with key and IV
  const decipher = crypto.createDecipheriv(
    ALGORITHM,
    Buffer.from(encryptionKey, 'hex'), // 32-byte hex string
    iv
  );

  // Decrypt the token
  let decrypted = decipher.update(encrypted, 'hex', 'utf8');
  decrypted += decipher.final('utf8');

  return decrypted;
}

/**
 * Validates that encryption key is properly configured
 * @returns true if encryption is properly configured
 */
export function validateEncryptionConfig(): boolean {
  const encryptionKey = process.env.ENCRYPTION_KEY;
  
  if (!encryptionKey) {
    return false;
  }

  try {
    const keyBuffer = Buffer.from(encryptionKey, 'base64');
    return keyBuffer.length >= 32; // Need at least 32 bytes for AES-256
  } catch {
    return false;
  }
}