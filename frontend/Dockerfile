FROM node:18-alpine
WORKDIR /app

# Copy manifests from the frontend directory (build context is the repo root)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Copy the frontend source into the container image
COPY frontend/ ./
RUN npm run build

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
