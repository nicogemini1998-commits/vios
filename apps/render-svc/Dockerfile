FROM node:20-slim
WORKDIR /app
COPY apps/render-svc/package.json ./
COPY apps/render-svc/src ./src
EXPOSE 4010
CMD ["node", "src/index.js"]
