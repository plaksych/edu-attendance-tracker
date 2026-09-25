FROM node:24.21.0-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci \
    --maxsockets=1 \
    --fetch-retries=5 \
    --fetch-retry-mintimeout=2000 \
    --fetch-retry-maxtimeout=60000

COPY index.html vite.config.ts tsconfig*.json ./
COPY src ./src
COPY public ./public
ARG VITE_STATIC_DATA=false
ENV VITE_STATIC_DATA=$VITE_STATIC_DATA
RUN if [ "$VITE_STATIC_DATA" = "false" ]; then rm -rf public/demo-data.json public/recognition-demo; fi
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:4714e0b1b2577eaa1a6131d07c958b67f0eb68e6d0521e90c6e5287db8cf0bc5

COPY nginx.conf /etc/nginx/conf.d/default.conf
USER root
RUN apk upgrade --no-cache \
    && sed -i 's/listen 80;/listen 8080;/g' /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
