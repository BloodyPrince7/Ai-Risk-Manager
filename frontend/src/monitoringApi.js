import { useCallback, useEffect, useRef, useState } from "react";

export async function requestJson(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("Could not reach the server. Check that the API is running, then try again.", { cause: error });
  }
  const data = await response.json();
  if (response.status === 503 && typeof data.detail === "string" && data.detail.startsWith("Incoming requests are paused")) {
    throw new Error("New requests are paused. No return case was created. Resume requests below or wait for the pause to end.");
  }
  if (!response.ok) throw new Error(data.detail?.[0]?.msg || data.detail || "Monitoring request failed.");
  return data;
}

export const post = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
export const timestamp = (value) => new Date(value).toLocaleString();
export const signalLabel = (field) => ({ account_id: "Customer account", device_id: "Device", ip_address: "IP address", location: "City or region", payment_token: "Payment reference", address_token: "Address reference", claim_type: "Return reason", product_category: "Product category" }[field] || field);

export const sourceLabel = (source) => ({ all: "All requests", live: "Customer requests", demo: "Test requests" }[source] || source);

export function useMonitor(apiUrl, path) {
  const [entry, setEntry] = useState(null);
  const [failure, setFailure] = useState(null);
  const sequence = useRef(0);
  const refresh = useCallback(async (signal) => {
    const current = ++sequence.current;
    try {
      const data = await requestJson(`${apiUrl}${path}`, { signal });
      if (current === sequence.current) { setEntry({ path, data }); setFailure(null); }
    } catch (error) {
      if (error.name !== "AbortError" && current === sequence.current) setFailure({ path, message: error.message });
    }
  }, [apiUrl, path]);
  useEffect(() => {
    const controller = new AbortController();
    const initial = window.setTimeout(() => refresh(controller.signal), 0);
    const timer = window.setInterval(() => refresh(controller.signal), 5000);
    return () => { controller.abort(); window.clearTimeout(initial); window.clearInterval(timer); };
  }, [refresh]);
  return { data: entry?.path === path ? entry.data : null, error: failure?.path === path ? failure.message : "", refresh };
}
