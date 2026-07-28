FROM node:22-slim AS build
WORKDIR /srv/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
# The Trust Panel page lives outside frontend/ so the multi_model_trust
# directory stays self-contained; vite reaches it through the @trust alias.
COPY multi_model_trust/ui/ /srv/multi_model_trust/ui/
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /srv/frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
