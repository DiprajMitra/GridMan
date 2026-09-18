import axios, { type AxiosInstance } from 'axios';
import type { OptimizationRequest, OptimizationResponse, HealthResponse } from '../types/energy';

let baseURL = (import.meta.env?.VITE_API_BASE_URL as string) || 'https://gridman.onrender.com';
let apiClient: AxiosInstance = createClient(baseURL, 30000);

// Dedicated client for /health: Render.com free tier spins down after 15 min
// of inactivity and cold-starts can take 30-60 s, so the default 30 s axios
// timeout was falsely reporting the live backend as offline. A separate
// longer-lived client with no-cache headers also prevents stale responses
// from being reused between polls.
function createClient(url: string, timeoutMs: number): AxiosInstance {
  return axios.create({
    baseURL: url,
    timeout: timeoutMs,
    headers: { 'Content-Type': 'application/json' },
  });
}

export function setBaseURL(url: string) {
  baseURL = url.replace(/\/+$/, '');
  apiClient = createClient(baseURL, 30000);
}

export function getBaseURL(): string {
  return baseURL;
}

export async function checkHealth(): Promise<HealthResponse> {
  // Bypass axios's shared client: we need a longer timeout and explicit
  // no-store cache headers for this probe only.
  const { data } = await axios.get<HealthResponse>(`${baseURL}/health`, {
    timeout: 90000,
    headers: { 'Cache-Control': 'no-store', Pragma: 'no-cache' },
  });
  return data;
}

export async function optimizeEnergy(
  request: OptimizationRequest
): Promise<OptimizationResponse> {
  const { data } = await apiClient.post<OptimizationResponse>(
    '/optimize-energy',
    request
  );
  return data;
}
