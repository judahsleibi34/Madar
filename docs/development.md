# Development

Use Docker Compose for the full local stack:

```sh
docker compose up -d --build
```

Run the backend directly during API development:

```sh
cd backend
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

Run the frontend directly during UI development:

```sh
cd frontend
npm install
npm run dev
```

The frontend production container serves the built React app through
`frontend/nginx.conf`, including SPA fallback routing for browser refreshes.
