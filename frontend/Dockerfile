ARG NODE_VERSION=22
FROM node:${NODE_VERSION}-alpine3.19
ENV NODE_ENV=production \
    NPM_CONFIG_LOGLEVEL=warn \
    NPM_CONFIG_COLOR=false \
    NPM_CACHE_FOLDER=/tmp/.npm-cache

WORKDIR /app

RUN --mount=type=cache,target=/tmp/.npm-cache \
    --mount=type=bind,source=package.json,target=package.json \
    --mount=type=bind,source=package-lock.json,target=package-lock.json \
    npm ci --cache /tmp/.npm-cache --prefer-offline --production=false

COPY . /app

RUN --mount=type=cache,target=/tmp/.npm-cache \
    npm ci --cache /tmp/.npm-cache --prefer-offline --production=false
