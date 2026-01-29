# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Build argument for git commit SHA
ARG GIT_COMMIT=unknown

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY . .

# Build
RUN npm run build

# Create version.json with build info
RUN echo "{\"ui_build\":\"${GIT_COMMIT}\",\"build_time\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > dist/version.json

# Production stage
FROM nginx:alpine

# Copy build output
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
