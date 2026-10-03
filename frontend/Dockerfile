FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Must match CLINIC_TIMEZONE on the backend. Vite bakes it into the bundle at build time.
ARG VITE_CLINIC_TIMEZONE=Asia/Colombo
ENV VITE_CLINIC_TIMEZONE=$VITE_CLINIC_TIMEZONE
RUN npm run build

FROM caddy:2-alpine

COPY --from=build /app/dist /srv
