const BASE_URL = "https://gridman.onrender.com";

// 1. Health check poll
export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/health`);
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === "ok";
  } catch (err) {
    console.error("Backend health check failed:", err);
    return false;
  }
}

// 2. Main energy optimization dispatch
export async function optimizeEnergy(payload: any) {
  const res = await fetch(`${BASE_URL}/optimize-energy`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`Optimization failed (${res.status}): ${errorBody}`);
  }

  return await res.json();
}
