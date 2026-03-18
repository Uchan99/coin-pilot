FROM node:18-alpine AS deps
WORKDIR /app

COPY frontend/next-dashboard/package.json frontend/next-dashboard/package-lock.json* ./
RUN npm install

FROM node:18-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY frontend/next-dashboard ./
RUN mkdir -p public \
    && npm run build

FROM node:18-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

# 비root 사용자로 실행 — 컨테이너 탈출 시 권한 최소화
RUN addgroup --system --gid 1001 app \
    && adduser --system --uid 1001 --ingroup app app

COPY --from=builder --chown=app:app /app/.next/standalone ./
COPY --from=builder --chown=app:app /app/.next/static ./.next/static
COPY --from=builder --chown=app:app /app/public ./public

USER app
EXPOSE 3000
CMD ["node", "server.js"]
