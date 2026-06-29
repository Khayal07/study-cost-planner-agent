FROM node:20-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY package.json package-lock.json* .npmrc* ./
RUN npm install

COPY . .

# Build the production bundle (NEXT_PUBLIC_* vars are inlined here)
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

# Run as the non-root 'node' user that ships with the base image.
RUN chown -R node:node /app
USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"

CMD ["npm", "start"]
