# Pantau Tular Backend

A Django-based backend for the Pantau Tular application.

## Containerization Guide

### Prerequisites

- Docker and Docker Compose installed on your machine
- Git repository cloned locally

### Development Setup

1. Copy the example environment file:
   ```
   cp .env.example .env
   ```

2. Update the `.env` file with your configuration values.

3. Build and start the containers:
   ```
   docker-compose up --build
   ```

4. Access the application at http://localhost:8000

### Production Deployment

1. Build the Docker image:
   ```
   docker build -t pantautular-backend .
   ```

2. Run the container:
   ```
   docker run -p 8000:8000 --env-file .env pantautular-backend
   ```

### Environment Variables

Make sure to set these environment variables in your `.env` file:

- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Django secret key
- `SECRET_API_KEY`: API key for authentication
- `EMAIL_HOST_USER`: Email for sending notifications
- `EMAIL_HOST_PASSWORD`: Password for the email account
- `PORT`: Port to run the application (default: 8000)

## Using with External PostgreSQL Database

If you're using an external PostgreSQL database (like Railway), set the `DATABASE_URL` environment variable to your database connection string and remove the `db` service from your deployment.

