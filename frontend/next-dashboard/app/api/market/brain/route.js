import { proxyToBackend } from "@/lib/api-proxy";

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const qs = searchParams.toString();
  return proxyToBackend(`/api/mobile/brain${qs ? `?${qs}` : ""}`);
}
