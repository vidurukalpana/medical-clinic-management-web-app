# Builds the React app, then serves it with Caddy, which also forwards /api to the backend.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Must match CLINIC_TIMEZONE on the backend.
ARG VITE_CLINIC_TIMEZONE=Asia/Colombo
ENV VITE_CLINIC_TIMEZONE=$VITE_CLINIC_TIMEZONE
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
