FROM node:20-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# Build the production bundle (NEXT_PUBLIC_* vars are inlined here)
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
