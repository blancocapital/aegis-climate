# Frontend

A Vite + React + TypeScript SPA for the Aegis Climate control tower.

## Getting started

```bash
cd frontend
npm install
npm run dev
```

Set the API base with `VITE_API_URL` (defaults to `http://localhost:8000`). During dev a Vite proxy maps `/api` to the same target.

## Auth defaults

Seeded demo credentials:
- tenant_id: `demo`
- email: `admin@demo.com`
- password: `password`

Tokens are stored in `localStorage`; a 401 response clears the token and redirects to `/login`.
