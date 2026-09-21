# Deploying the frontend

This is a standard Next.js app — deployable anywhere that runs Node.js.
**Vercel** is the natural fit (it's what Next.js itself is built by/for, and
has a generous free tier for a project this size), but Render, Netlify, or
any other Node host works too.

## Steps (Vercel)

1. Push this `frontend-next/` folder to its own GitHub repo (or a subfolder
   of the same repo as the backend — Vercel supports setting a "Root
   Directory" if so).
2. In Vercel: **New Project** → import that repo → it auto-detects Next.js,
   no config needed.
3. Add the environment variable before deploying: `NEXT_PUBLIC_API_BASE_URL`
   = your backend's URL (e.g. `https://thesis-compliance-demo.onrender.com`,
   no trailing slash).
4. Deploy.

## The one thing you must also do on the backend

Once you know the frontend's URL (Vercel gives you one like
`https://thesis-compliance-frontend.vercel.app`), the backend needs to allow
it in CORS, or the browser will block every API call with a CORS error.

On Render, open the `thesis-compliance-demo` service → **Environment** →
set `ALLOWED_ORIGINS` to that exact URL (comma-separate if you also want
`http://localhost:3000` for local frontend development against the live
backend):

```
ALLOWED_ORIGINS=https://thesis-compliance-frontend.vercel.app,http://localhost:3000
```

Save — Render redeploys automatically. Without this step, the dashboard will
load but every data request will fail silently with a CORS error visible
only in the browser console (F12 → Console) — worth checking there first if
the frontend looks stuck on "Loading…".
