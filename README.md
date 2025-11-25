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
- `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`: Grafana credentials used by Docker Compose

## Using with External PostgreSQL Database

If you're using an external PostgreSQL database (like Railway), set the `DATABASE_URL` environment variable to your database connection string and remove the `db` service from your deployment.

## Monitoring (Prometheus + Grafana)

This project ships with a ready-to-run monitoring stack that scrapes the built-in Django Prometheus metrics (`/metrics/`) and visualizes them in Grafana.

1. Ensure your `.env` file contains `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD`. Defaults are `admin/admin`.
2. Start the monitoring stack alongside the backend:
   ```bash
   docker-compose up --build web prometheus grafana
   ```
3. Prometheus UI: http://localhost:9090
   - Go to **Status -> Targets** and confirm the `django` job is `UP`. Metrics can be queried via **Graph** (e.g., `django_http_requests_total`).
4. Grafana UI: http://localhost:3001
   - Log in with the credentials from `.env`.
   - The Prometheus data source is provisioned automatically. You can import a dashboard (e.g., Grafana.com ID `1860` for Django/WSGI metrics) or create panels from the available metrics.
5. Django metrics endpoint (for quick checks) remains available at http://localhost:8000/metrics/.

Prometheus stores time-series data under the `prometheus_data` Docker volume, while Grafana dashboards/configurations persist in the `grafana_data` volume.

## Versioning and Releases

This project follows [Semantic Versioning](https://semver.org/). Version numbers follow the pattern: MAJOR.MINOR.PATCH.

- **MAJOR**: Incompatible API changes
- **MINOR**: Add functionality in a backward-compatible manner
- **PATCH**: Backward-compatible bug fixes

### Current Version

Check the [VERSION](./VERSION) file for the current version.

### Release Process

Releases are managed through GitHub Actions:

1. Go to the "Actions" tab in the GitHub repository
2. Select the "Create Release" workflow
3. Click "Run workflow"
4. Choose the version type (major, minor, patch)
5. Click "Run workflow"

This will:
- Increment the version number
- Create a Git tag
- Generate a GitHub release
- Trigger the Docker image build with the new version tag

## Branching Strategy

The project uses the following branches:

### Main Branch
- Production-ready code
- Deployed automatically to the production environment
- Tagged releases are created from this branch
- Docker images are tagged as `latest`

### Staging Branch
- Pre-production testing environment
- Deployed automatically to the staging environment
- Releases are tagged with `-staging` suffix
- Docker images are tagged as `staging`

### Feature Branches
- Created for new features or bug fixes
- Should branch off from `staging`
- Pull requests should target the `staging` branch

