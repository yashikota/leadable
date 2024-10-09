FROM node:22-alpine3.19

WORKDIR /app

COPY package.json .
RUN yarn install
RUN yarn global add @vue/cli

USER node
