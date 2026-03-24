/*
 * 서버-사이드 API 프록시 헬퍼
 * Client Component → Next.js Route Handler → 백엔드 bot:8000
 *
 * 브라우저는 Docker 내부 주소(bot:8000)에 접근 불가하므로,
 * Next.js 서버가 중계하여 API Secret도 서버에서만 관리한다.
 */

const BOT_API_BASE_URL = (process.env.BOT_API_BASE_URL || "http://bot:8000").replace(/\/+$/, "");
const API_SECRET = process.env.COINPILOT_API_SHARED_SECRET || "";
const SHARED_SECRET_HEADER = "X-Api-Secret";

/**
 * 백엔드 API를 호출하고 결과를 NextResponse로 반환
 * @param {string} path - 백엔드 경로 (예: "/api/mobile/candles?symbol=KRW-BTC")
 * @param {object} options - fetch 옵션 (method, body 등)
 */
export async function proxyToBackend(path, options = {}) {
  const headers = { accept: "application/json", ...options.headers };
  if (API_SECRET) headers[SHARED_SECRET_HEADER] = API_SECRET;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);

  try {
    const res = await fetch(`${BOT_API_BASE_URL}${path}`, {
      ...options,
      headers,
      cache: "no-store",
      signal: controller.signal,
    });

    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch (error) {
    return Response.json(
      { ok: false, error: error?.message || "Backend proxy failed" },
      { status: 502 },
    );
  } finally {
    clearTimeout(timer);
  }
}
