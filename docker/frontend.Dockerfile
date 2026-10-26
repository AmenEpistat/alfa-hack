FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS build
WORKDIR /app/client
COPY client/package.json client/package-lock.json client/.npmrc ./
RUN npm ci --registry=https://registry.npmjs.org/
COPY client ./
ARG VITE_API_URL=/api
ARG VITE_SYNTHETIC_MODE=false
ENV VITE_API_URL=${VITE_API_URL}
ENV VITE_SYNTHETIC_MODE=${VITE_SYNTHETIC_MODE}
RUN npm run build

FROM nginx:1.28-alpine@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/client/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/
