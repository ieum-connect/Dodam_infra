FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY src ./src
COPY public ./public
COPY index.html vite.config.js ./
ENV VITE_API_BASE_URL=""
RUN npm run build
FROM nginx:1.28-alpine
COPY --from=build /app/dist /usr/share/nginx/html
RUN rm /etc/nginx/conf.d/default.conf
EXPOSE 80 443
