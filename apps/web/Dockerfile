FROM node:22-alpine
WORKDIR /workspace
COPY package*.json ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/shared-types/package.json ./packages/shared-types/package.json
COPY packages/ui/package.json ./packages/ui/package.json
COPY packages/config/package.json ./packages/config/package.json
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--workspace", "@syre/web"]
