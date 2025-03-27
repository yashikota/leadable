FROM node:22-slim AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable
COPY . /app
WORKDIR /app

ARG VITE_SERVER_ADDRESS
ENV VITE_SERVER_ADDRESS=${VITE_SERVER_ADDRESS}

FROM base AS prod-deps
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --prod --frozen-lockfile

FROM base AS build
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile
RUN pnpm run build

FROM caddy:2.9.1-alpine
COPY --from=build /app/dist /srv
EXPOSE 8877
CMD ["caddy", "file-server", "-r", "/srv", "-l", ":8877"]
