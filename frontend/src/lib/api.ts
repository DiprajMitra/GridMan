import axios, { type AxiosInstance } from 'axios';
import type { OptimizationRequest, OptimizationResponse, HealthResponse } from '../types/energy';

let baseURL = (import.meta.env?.VITE_API_BASE_URL as string) || 'https://gridman.onrender.com';
let apiClient: AxiosInstance = createClient(baseURL);

function createClient(url: string): AxiosInstance {
  return axios.create({
    baseURL: url,
    timeout: 30000,
    headers: { 'Content-Type': 'application/json' },
  });
}

export function setBaseURL(url: string) {
  baseURL = url.replace(/\/+$/, '');
  apiClient = createClient(baseURL);
}

export function getBaseURL(): string {
  return baseURL;
}

export async function checkHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/health');
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
