FROM node:24-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci \
    --maxsockets=1 \
    --fetch-retries=5 \
    --fetch-retry-mintimeout=2000 \
    --fetch-retry-maxtimeout=60000

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
