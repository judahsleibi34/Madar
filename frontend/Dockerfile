FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS build

WORKDIR /app

ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

COPY package*.json ./

RUN npm ci

COPY . .

RUN npm run build

FROM nginx:alpine@sha256:4a73073bd557c65b759505da037898b61f1be6cbcc3c2c3aeac22d2a470c1752

RUN rm -f /etc/nginx/conf.d/default.conf \
    && mkdir -p /etc/nginx/templates/includes /etc/nginx/conf.d/includes /var/cache/nginx \
    && sed -i '/^user[[:space:]]/d; s!^pid[[:space:]].*;!pid /tmp/nginx.pid;!' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /etc/nginx/conf.d /etc/nginx/templates /var/cache/nginx
COPY --chown=nginx:nginx --from=build /app/dist /usr/share/nginx/html
COPY --chown=nginx:nginx nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --chown=nginx:nginx security_headers.conf.template /etc/nginx/templates/includes/security_headers.conf.template

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
