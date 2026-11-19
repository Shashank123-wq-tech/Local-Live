# LocaleLive
### Agentic AI Search for Local Services

> Find places across Toronto through natural language.

**Live Demo**: [localelive.vercel](https://frontend-local-live.vercel.app/)  

LocaleLive is an AI-powered local search application. Ask for a service in ordinary language, and the application interprets the request, searches place data, and returns relevant results with location context.

## What the Application Does

- Accepts natural-language requests for local services.
- Uses a multi-agent workflow to classify requests, retrieve relevant places, generate an answer, and review the response.
- Uses semantic search over service descriptions with Hugging Face embeddings and Milvus Lite.
- Stores place records in MongoDB Atlas and supports location-based retrieval.
- Uses routing, maps, and web search integrations where configured.
- Runs as Docker containers for deployment on AWS.

## Toronto Dataset

The Toronto dataset is prepared from public place records and mapped to the service categories used by the application.

The preparation workflow includes:

- Filtering place records against the selected Bengaluru boundary.
- Mapping source categories to the application’s service categories.
- Reviewing suspicious category assignments and duplicate candidates.
- Preserving source identifiers and provenance where available.
- Keeping missing ratings, opening hours, and occupancy as unknown rather than inventing values.

Dataset counts, quality metrics, and category coverage should be added here after the final MongoDB import and validation. Do not treat source confidence as a business rating or verified operating status.

## Agent Workflow

A query flows through the application’s agent graph:

1. **Classifier** identifies whether the user is greeting, searching for a service, or asking a general question.
2. **Retriever** searches the local place data using service and location information.
3. **External search** uses configured integrations for open-ended questions or areas without local records.
4. **Generator** prepares a response based on retrieved context.
5. **Reviewer** checks the response and can request refinement before it is returned.

The graph and prompts are implemented in the backend’s graph and agent modules.

## Technology

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 18, TypeScript, Tailwind CSS |
| Authentication | Clerk |
| Map display | Mapbox GL |
| Backend API | Python 3.11, FastAPI |
| Agent workflow | LangGraph and LangChain |
| Language model | Groq |
| Place database | MongoDB Atlas |
| Vector database | Milvus Lite |
| Embeddings | Hugging Face Inference API |
| Routing | OpenRouteService |
| Web search | Tavily |
| Containerization | Docker and Docker Compose |
| Hosting | AWS EC2 with Docker |

## Repository Layout

```text
.
├── backend/
│   ├── src/
│   │   ├── agents/
│   │   ├── graph_init.py
│   │   └── agents_prompt.py
│   ├── requirements_pip.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   ├── components/
│   ├── package.json
│   └── Dockerfile
├── infra/
│   ├── ARCHITECTURE.md
│   └── ...
├── docker-compose.yml
└── README.md
```

Adjust this tree if your checked-out repository has different paths.

## Configuration

Create backend and frontend environment files from the example files. Use real values locally and store production secrets in a secure environment on AWS. Do not commit `.env` files or real API keys.

### Backend environment

```dotenv
GROQ_API_KEY=
LLM_MODEL=

MONGODB_URL=
POSTGRES_URL=

HF_API_KEY=
MILVUS_DB_PATH=/data/milvus/milvus.db

GOOGLE_MAPS_API_KEY=
ORS_API_KEY=
TAVILY_API_KEY=

CLERK_JWKS_URL=
CORS_ORIGINS=http://localhost:3000
ENVIRONMENT=development
LOG_LEVEL=INFO

LANGCHAIN_API_KEY=
LANGCHAIN_TRACING_V2=false
```

Set `CORS_ORIGINS` to the deployed frontend origin in production, for example:

```dotenv
CORS_ORIGINS=https://app.example.com
ENVIRONMENT=production
```

### Frontend environment

```dotenv
NEXT_PUBLIC_BACKEND_URL=http://localhost:8001
NEXT_PUBLIC_MAPBOX_TOKEN=
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=

NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL=/
```

`NEXT_PUBLIC_*` values are embedded in the frontend during `next build`. Set the production backend URL, Mapbox token, and Clerk publishable key before building the production frontend image. Keep `CLERK_SECRET_KEY` private and provide it only to the running frontend server.

For production, use the Clerk keys and JWKS URL from the same production Clerk instance.

## Local Development with Docker

Prerequisites:

- Docker Desktop with Docker Compose enabled.
- Backend and frontend environment files populated.
- Access to the required external services and databases.

From the repository root, start the application:

```powershell
docker compose up --build -d
```

Check container status:

```powershell
docker compose ps
```

Follow logs:

```powershell
docker compose logs -f
```

Open the application and API documentation:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8001`
- API docs: `http://localhost:8001/docs`

Stop the stack:

```powershell
docker compose down
```

If your Compose file has a different name, pass it with `-f`, for example:

```powershell
docker compose -f docker-compose.local.yml up --build -d
```

## Production Deployment on AWS with Docker

This deployment uses an AWS EC2 instance to run Docker containers. A reverse proxy handles public HTTPS traffic and routes requests to the frontend and backend containers.

### 1. Prepare AWS

Create an EC2 instance with a supported Linux image and install Docker Engine and the Docker Compose plugin.

Configure the instance security group to allow:

| Port | Source | Use |
|---|---|---|
| 22 | Your current IP only | SSH administration |
| 80 | `0.0.0.0/0` and `::/0` | HTTP and certificate validation |
| 443 | `0.0.0.0/0` and `::/0` | HTTPS application traffic |

Do not expose the frontend or backend container ports publicly when a reverse proxy is used.

Allocate and associate an Elastic IP with the instance so its public address remains stable.

### 2. Configure DNS

Use a domain you own and can edit. Create DNS records that point your application hostnames to the Elastic IP:

| Record type | Host | Value |
|---|---|---|
| A | `app` | Your EC2 Elastic IP |
| A | `api` | Your EC2 Elastic IP |

The example hostnames become:

- Frontend: `https://app.example.com`
- Backend: `https://api.example.com`

Replace `example.com` with your registered domain. DNS can be managed by your domain registrar or Route 53.

### 3. Configure the reverse proxy

Use a reverse proxy such as Caddy to send each hostname to the correct Docker service. For example:

```caddyfile
app.example.com {
    reverse_proxy frontend:3000
}

api.example.com {
    reverse_proxy backend:8000
}
```

The service names and internal ports must match your Docker Compose configuration. Caddy can obtain and renew HTTPS certificates when the DNS records are correct and ports 80 and 443 reach the proxy.

### 4. Set production variables

Set the frontend production values before building:

```dotenv
NEXT_PUBLIC_BACKEND_URL=https://api.example.com
NEXT_PUBLIC_MAPBOX_TOKEN=
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
```

Set backend production values:

```dotenv
CORS_ORIGINS=https://app.example.com
CLERK_JWKS_URL=
ENVIRONMENT=production
```

Add all remaining backend credentials required by the application. Do not put backend secrets in the frontend image or in `NEXT_PUBLIC_*` variables.

### 5. Configure Clerk production

In the Clerk dashboard:

1. Create or select the production instance.
2. Set the application domain to the frontend hostname.
3. Add the DNS records Clerk provides at the active DNS provider.
4. Verify the domain in Clerk.
5. Copy the production publishable key, secret key, and JWKS URL into the correct frontend or backend settings.
6. Add the frontend domain to the backend CORS origins.

The frontend and backend must use configuration from the same Clerk production instance.

### 6. Build and start the containers

Copy the repository to EC2 using your chosen deployment workflow. From the directory containing the production Docker Compose file:

```bash
docker compose build
docker compose up -d
docker compose ps
```

Review logs if a service does not start:

```bash
docker compose logs --tail=200
```

After changing frontend `NEXT_PUBLIC_*` variables, rebuild the frontend image:

```bash
docker compose build --no-cache frontend
docker compose up -d frontend
```

### 7. Verify the deployment

Check each item:

- `https://app.example.com` loads with a valid certificate.
- `https://api.example.com/docs` responds if public API documentation is enabled.
- Sign-up and sign-in work through the production Clerk instance.
- An authenticated search request reaches the backend.
- The backend can connect to MongoDB Atlas, PostgreSQL, Milvus, and configured external APIs.
- Logs contain no missing environment variables or database connection errors.

## Operational Notes

- Keep MongoDB Atlas network access restricted to the deployment’s required source addresses.
- Persist Milvus data using a Docker volume if it must survive container recreation.
- Back up databases and configuration separately from the application container.
- Monitor container health, disk usage, memory usage, and external API limits.
- Avoid logging API keys, authentication tokens, or full database connection strings.
- Do not mark a place as verified open when operating status is unknown.
- Do not fabricate ratings, opening hours, or occupancy values when the source has no value.


## License

Apache License 2.0. See [LICENSE](LICENSE).
