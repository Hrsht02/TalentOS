# TalentOS Frontend

React + Vite SPA. Deploy to Vercel with the project root set to `frontend`.

- Build command: `npm run build`
- Output directory: `dist`
- Environment variable: `VITE_API_BASE_URL=https://YOUR-RENDER-SERVICE.onrender.com/api/v1`

The Vercel SPA rewrite is in `vercel.json`. Do not add API keys to frontend environment variables; every `VITE_*` value is public.
