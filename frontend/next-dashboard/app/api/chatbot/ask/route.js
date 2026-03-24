import { proxyToBackend } from "@/lib/api-proxy";

export async function POST(request) {
  const body = await request.text();
  return proxyToBackend("/api/mobile/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
}
