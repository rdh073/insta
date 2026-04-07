# Panduan Instalasi InstaManager

Panduan ini menjelaskan cara menginstal dan menjalankan **InstaManager** (backend + frontend) di **Windows 11** dan **Ubuntu**.

---

## Daftar Isi

1. [Prasyarat](#prasyarat)
2. [Clone Repositori](#clone-repositori)
3. [Arsitektur Proyek](#arsitektur-proyek)
4. [Instalasi Backend](#instalasi-backend)
   - [Windows 11](#backend--windows-11)
   - [Ubuntu](#backend--ubuntu)
5. [Instalasi Frontend](#instalasi-frontend)
   - [Windows 11](#frontend--windows-11)
   - [Ubuntu](#frontend--ubuntu)
6. [Konfigurasi Environment](#konfigurasi-environment)
   - [Backend `.env`](#backend-env)
   - [Frontend `.env`](#frontend-env)
7. [Database & Migrasi](#database--migrasi)
8. [AI Provider Setup](#ai-provider-setup)
9. [Menjalankan Aplikasi](#menjalankan-aplikasi)
   - [Development](#development)
   - [Production Build](#production-build)
10. [Verifikasi Instalasi](#verifikasi-instalasi)
11. [Fitur & Konfigurasi Lanjutan](#fitur--konfigurasi-lanjutan)
12. [Keamanan & Akses](#keamanan--akses)
13. [Troubleshooting](#troubleshooting)

---

## Prasyarat

Pastikan semua perangkat lunak berikut sudah terinstal sebelum melanjutkan.

| Perangkat Lunak | Versi Minimum | Keterangan |
|----------------|---------------|------------|
| Python | 3.12 | Backend runtime (pinned di `.python-version`) |
| pip | 24.x | Python package manager |
| Node.js | 20.x LTS | Frontend runtime |
| npm | 10.x | Node package manager |
| Git | 2.x | Version control |

### Opsional (production)

| Perangkat Lunak | Keterangan |
|----------------|------------|
| PostgreSQL 15+ | Database persisten (alternatif dari SQLite/memory) |
| Nginx / Caddy | Reverse proxy untuk production |
| systemd / NSSM | Process manager |

### Cek versi yang terinstal

```bash
python --version        # atau python3 --version di Ubuntu
pip --version
node --version
npm --version
git --version
```

---

## Clone Repositori

```bash
git clone <url-repositori>
cd insta
```

---

## Arsitektur Proyek

```
insta/
├── backend/                    # FastAPI Python backend
│   ├── app/                    # Aplikasi utama
│   │   ├── main.py             # Entry point (uvicorn)
│   │   ├── adapters/           # Adapter layer (HTTP, persistence, AI, Instagram)
│   │   │   ├── http/routers/   # REST API endpoints
│   │   │   ├── ai/             # AI provider adapters, tool registry
│   │   │   ├── instagram/      # Instagram API client (instagrapi)
│   │   │   ├── persistence/    # SQLAlchemy repositories
│   │   │   └── scheduler/      # Job queue
│   │   ├── application/        # Use cases & business logic
│   │   │   ├── use_cases/      # Account, post, relationship, identity, etc.
│   │   │   └── ports/          # Abstract interfaces (clean architecture)
│   │   └── bootstrap/          # Dependency injection & wiring
│   ├── ai_copilot/             # AI Copilot & Smart Engagement module
│   │   ├── application/        # Graph definitions, nodes, state, policies
│   │   │   ├── graphs/         # LangGraph workflow topologies
│   │   │   ├── smart_engagement/ # Smart engagement ports, state, nodes
│   │   │   └── use_cases/      # Run copilot, run smart engagement
│   │   └── adapters/           # Copilot-specific adapters
│   │       ├── circuit_breaker.py    # Circuit breaker infrastructure
│   │       ├── engagement_memory_adapter.py  # LangGraph Store memory
│   │       └── copilot_memory_adapter.py     # Copilot cross-thread memory
│   ├── alembic/                # Database migrations
│   ├── sessions/               # Runtime session files (auto-created)
│   ├── requirements.txt        # Python dependencies
│   └── .env.example            # Environment template
│
├── frontend/                   # React + Vite SPA
│   ├── src/
│   │   ├── pages/              # Page components (thin shells)
│   │   ├── features/           # Feature-colocated modules
│   │   │   ├── relationships/  # Follow/unfollow/cross-follow feature
│   │   │   │   ├── components/ # ActionTab, CrossFollowTab, AccountChip, ResultRow
│   │   │   │   ├── hooks/      # useFollowAction, useCrossFollow
│   │   │   │   └── types/      # JobResult, CrossFollowPair
│   │   │   └── proxy/          # Proxy management feature
│   │   │       └── components/ # AccountRoutingTab, ProxyPoolTab, ProxyTestChip
│   │   ├── components/         # Shared UI (Button, Card, Modal, Input, PageHeader)
│   │   ├── store/              # Zustand state stores
│   │   ├── api/                # API client modules (axios)
│   │   ├── types/              # Shared TypeScript types
│   │   └── hooks/              # Shared custom hooks
│   ├── package.json
│   └── .env.example
│
├── docs/                       # Dokumentasi
├── tests/                      # Test suite (pytest)
├── scripts/                    # Shell scripts
│   ├── start.sh                # Jalankan backend + frontend sekaligus (Linux/macOS)
│   ├── install.sh              # Instalasi otomatis (Linux/macOS)
│   ├── install.ps1             # Instalasi otomatis (Windows)
│   └── docker-install.sh       # Instalasi via Docker
```

### Stack Teknologi

| Layer | Teknologi |
|-------|-----------|
| **Backend Framework** | FastAPI 0.115 + Uvicorn |
| **Instagram API** | instagrapi 2.3 |
| **AI Orchestration** | LangGraph (graph-based workflows) |
| **AI Providers** | OpenAI, Gemini, DeepSeek, Anthropic (Claude) |
| **Database** | SQLAlchemy 2.0 + Alembic (memory/SQLite/PostgreSQL) |
| **Frontend Framework** | React 19 + TypeScript 5.9 |
| **Build Tool** | Vite 8 |
| **Styling** | Tailwind CSS 4.2 (Tokyo Night theme) |
| **State Management** | Zustand 5 |

---

## Instalasi Backend

### Backend — Windows 11

Buka **PowerShell** atau **Command Prompt** sebagai Administrator.

#### 1. Instal Python 3.12

Unduh dari [python.org](https://www.python.org/downloads/) dan jalankan installer.
Pastikan centang **"Add Python to PATH"** saat instalasi.

Verifikasi:
```powershell
python --version
```

#### 2. Buat dan aktifkan virtual environment

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
```

> Jika muncul error eksekusi script, jalankan perintah ini terlebih dahulu:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

#### 3. Instal dependensi

```powershell
pip install -r requirements.txt
```

#### 4. Konfigurasi environment

```powershell
copy .env.example .env
```

Edit `.env` sesuai kebutuhan (lihat [Konfigurasi Environment](#konfigurasi-environment)).

---

### Backend — Ubuntu

Buka **Terminal**.

#### 1. Instal Python 3.12

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip
```

Verifikasi:
```bash
python3.12 --version
```

#### 2. Buat dan aktifkan virtual environment

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
```

#### 3. Instal dependensi

```bash
pip install -r requirements.txt
```

#### 4. Konfigurasi environment

```bash
cp .env.example .env
```

Edit `.env` sesuai kebutuhan (lihat [Konfigurasi Environment](#konfigurasi-environment)).

---

## Instalasi Frontend

### Frontend — Windows 11

#### 1. Instal Node.js

Unduh **Node.js 20 LTS** dari [nodejs.org](https://nodejs.org/) dan jalankan installer.

Verifikasi:
```powershell
node --version
npm --version
```

#### 2. Instal dependensi

```powershell
cd frontend
npm install
```

#### 3. Konfigurasi environment

```powershell
copy .env.example .env
```

---

### Frontend — Ubuntu

#### 1. Instal Node.js 20 LTS

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Verifikasi:
```bash
node --version
npm --version
```

#### 2. Instal dependensi

```bash
cd frontend
npm install
```

#### 3. Konfigurasi environment

```bash
cp .env.example .env
```

---

## Konfigurasi Environment

### Backend `.env`

File berada di `backend/.env`. Salin dari `backend/.env.example`.

#### Konfigurasi minimal untuk development

```env
# Persistence (gunakan memory untuk dev cepat)
PERSISTENCE_BACKEND=memory

# Minimal satu AI provider (untuk Copilot)
OPENAI_API_KEY=sk-...
```

Dengan konfigurasi di atas, backend sudah bisa berjalan. Semua fitur yang memerlukan database akan menggunakan in-memory storage (hilang saat restart).

#### Konfigurasi untuk production

```env
# Persistence menggunakan database
PERSISTENCE_BACKEND=sql
PERSISTENCE_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/instamanager

# Enkripsi untuk menyimpan session Instagram dan OAuth tokens
ENCRYPTION_KEY=<generate dengan perintah di bawah>

# CORS — isi dengan URL frontend production
APP_CORS_ORIGINS=https://yourdomain.com

# Matikan auto-reload
APP_UVICORN_RELOAD=false

# Durable checkpointer untuk AI copilot state
LANGGRAPH_CHECKPOINTER_BACKEND=sqlite
LANGGRAPH_CHECKPOINTER_SQLITE_PATH=sessions/langgraph_checkpoints.sqlite3
```

Generate `ENCRYPTION_KEY`:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

#### Referensi lengkap variabel backend

| Variabel | Default | Keterangan |
|----------|---------|------------|
| **Persistence** | | |
| `PERSISTENCE_BACKEND` | `memory` | `memory`, `sqlite`, atau `sql` |
| `PERSISTENCE_DATABASE_URL` | — | URL koneksi database (PostgreSQL/SQLite) |
| `PERSISTENCE_SQLITE_PATH` | — | Path file SQLite (fallback jika `DATABASE_URL` kosong) |
| `ENCRYPTION_KEY` | — | Kunci Fernet untuk enkripsi session dan token |
| `PERSISTENCE_POOL_SIZE` | `10` | Ukuran connection pool (non-SQLite) |
| `PERSISTENCE_MAX_OVERFLOW` | `20` | Max overflow connections |
| `PERSISTENCE_POOL_TIMEOUT_SECONDS` | `30` | Timeout menunggu connection dari pool |
| `PERSISTENCE_SQLITE_BUSY_TIMEOUT_MS` | `5000` | SQLite lock wait timeout |
| **AI Providers** | | |
| `OPENAI_API_KEY` | — | API key OpenAI (GPT-4, dll.) |
| `GEMINI_API_KEY` | — | API key Google Gemini |
| `DEEPSEEK_API_KEY` | — | API key DeepSeek |
| `ANTIGRAVITY_API_KEY` | — | API key Antigravity local proxy |
| **AI Provider OAuth (opsional)** | | |
| `OPENAI_CODEX_ACCESS_TOKEN` | — | OAuth access token untuk OpenAI Codex |
| `OPENAI_CODEX_REFRESH_TOKEN` | — | OAuth refresh token |
| `OPENAI_CODEX_EXPIRES_AT` | — | Token expiry timestamp |
| `OPENAI_CODEX_API_BASE_URL` | `https://api.openai.com/v1` | Base URL |
| `CLAUDE_CODE_ACCESS_TOKEN` | — | OAuth access token untuk Claude Code |
| `CLAUDE_CODE_REFRESH_TOKEN` | — | OAuth refresh token |
| `CLAUDE_CODE_EXPIRES_AT` | — | Token expiry timestamp |
| `CLAUDE_CODE_MAX_TOKENS` | `8096` | Max tokens per request |
| **Security** | | |
| `API_KEY` | — | Jika diisi, setiap request API harus menyertakan header `X-API-Key: <nilai>`. Set dari Settings > Connection di frontend. |
| `ENABLE_DASHBOARD_AUTH` | — | Set `true` untuk mengaktifkan halaman login. Memerlukan `ADMIN_PASSWORD` dan `AUTH_SECRET`. |
| `ADMIN_PASSWORD` | — | Password admin untuk login ke dashboard |
| `AUTH_SECRET` | — | Secret untuk signing JWT token. Gunakan string acak panjang, berbeda dari `ADMIN_PASSWORD`. |
| **Feature Flags** | | |
| `ENABLE_OPERATOR_COPILOT` | `1` | Aktifkan AI Copilot (`1`=on, `0`=off) |
| `SMART_ENGAGEMENT_EXECUTION_ENABLED` | `false` | Izinkan mode execute di smart engagement |
| `ENABLE_PROVIDER_OPENAI_CODEX` | `false` | Aktifkan OpenAI Codex provider |
| `ENABLE_PROVIDER_CLAUDE_CODE` | `false` | Aktifkan Claude Code provider |
| **HTTP Runtime** | | |
| `APP_CORS_ORIGINS` | — | Daftar origin yang diizinkan (pisah koma) |
| `APP_CORS_ALLOW_METHODS` | `GET,POST,...,OPTIONS` | HTTP methods yang diizinkan |
| `APP_CORS_ALLOW_HEADERS` | `Authorization,...` | Headers yang diizinkan |
| `APP_CORS_ALLOW_CREDENTIALS` | `true` | Izinkan credentials di CORS |
| `APP_REQUEST_LOGGING_ENABLED` | `true` | Aktifkan logging request HTTP |
| `APP_UVICORN_RELOAD` | `false` | Auto-reload saat kode berubah (dev only) |
| **LangGraph** | | |
| `LANGGRAPH_CHECKPOINTER_BACKEND` | `memory` | `memory` atau `sqlite` |
| `LANGGRAPH_CHECKPOINTER_SQLITE_PATH` | auto | Path file SQLite untuk checkpoints |
| **Audit Log (opsional)** | | |
| `SMART_ENGAGEMENT_AUDIT_LOG_PATH` | `/tmp/smart-engagement-audit.jsonl` | Path file audit log smart engagement |
| `OPERATOR_COPILOT_AUDIT_LOG_PATH` | auto | Path file audit log copilot |

---

### Frontend `.env`

File berada di `frontend/.env`. Salin dari `frontend/.env.example`.

```env
# URL backend — kosongkan untuk menggunakan proxy dev (localhost:8000)
VITE_BACKEND_URL=

# Target proxy dev server (default ke backend lokal)
VITE_DEV_PROXY_TARGET=http://127.0.0.1:8000

# Aktifkan sourcemap saat build (true/false)
VITE_BUILD_SOURCEMAP=false
```

#### Untuk production

```env
VITE_BACKEND_URL=https://api.yourdomain.com
VITE_BUILD_SOURCEMAP=false
```

> **Catatan:** Semua variabel frontend harus diawali `VITE_` agar terbaca oleh Vite. Variabel ini di-embed saat build time, bukan runtime.

---

## Database & Migrasi

### Mode Persistence

| Mode | `PERSISTENCE_BACKEND` | Keterangan | Cocok Untuk |
|------|----------------------|------------|-------------|
| **Memory** | `memory` | Semua data hilang saat restart | Dev cepat, testing |
| **SQLite** | `sqlite` | File-based, tanpa server | Dev persisten, single-user |
| **PostgreSQL** | `sql` | Full database server | Production, multi-worker |

### Setup PostgreSQL (production)

```bash
# Buat database
sudo -u postgres createdb instamanager
sudo -u postgres createuser --password instauser

# Set di .env
PERSISTENCE_BACKEND=sql
PERSISTENCE_DATABASE_URL=postgresql+psycopg://instauser:password@localhost:5432/instamanager
```

### Menjalankan Migrasi

Migrasi Alembic dijalankan otomatis saat backend start. Untuk menjalankan manual:

```bash
cd backend
source .venv/bin/activate

# Cek status migrasi saat ini
alembic current

# Upgrade ke versi terbaru
alembic upgrade head

# Rollback satu langkah
alembic downgrade -1
```

Migrasi yang tersedia:
- `001_baseline_schema` — Tabel dasar (accounts, sessions, jobs)
- `002_add_llm_configs` — Tabel konfigurasi LLM per-user
- `003_add_oauth_credentials` — Tabel credential OAuth (encrypted)

---

## AI Provider Setup

Minimal satu AI provider dibutuhkan untuk fitur Operator Copilot. Tanpa AI provider, fitur copilot dan smart engagement tidak akan berfungsi, tetapi fitur lain (akun, proxy, post) tetap berjalan.

### OpenAI (Direkomendasikan)

```env
OPENAI_API_KEY=sk-proj-...
```

Model default: `gpt-4o`. Daftar di [platform.openai.com](https://platform.openai.com/).

### Google Gemini

```env
GEMINI_API_KEY=AIza...
```

Model default: `gemini-2.0-flash`. Daftar di [aistudio.google.com](https://aistudio.google.com/).

### DeepSeek

```env
DEEPSEEK_API_KEY=sk-...
```

Model default: `deepseek-chat`. Daftar di [platform.deepseek.com](https://platform.deepseek.com/).

### Antigravity (Local Proxy)

Untuk menjalankan model lokal melalui OpenAI-compatible proxy:

```env
ANTIGRAVITY_API_KEY=your-key
```

Default base URL: `http://127.0.0.1:8045/v1`

### Ganti Provider di Runtime

Provider dan model bisa diganti dari UI **Settings** page atau per-request melalui Copilot API.

---

## Menjalankan Aplikasi

### Development

#### Ubuntu/macOS — Jalankan keduanya sekaligus

Dari direktori root proyek:

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

Script ini akan menjalankan:
- Backend di `http://localhost:8000`
- Frontend di `http://localhost:5173`

#### Jalankan secara terpisah (Windows 11 & Ubuntu)

**Terminal 1 — Backend:**

```bash
# Ubuntu
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env
```

```powershell
# Windows 11
cd backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env
```

> Tambahkan `--reload` untuk auto-restart saat kode berubah (development only).

**Terminal 2 — Frontend:**

```bash
cd frontend
npm run dev
```

Akses aplikasi di browser: **http://localhost:5173**

---

### Production Build

#### Backend (production)

```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --env-file .env
```

> **Rekomendasi:** Jalankan uvicorn di belakang reverse proxy (Nginx/Caddy) dan gunakan proses manager seperti `systemd` (Ubuntu) atau `NSSM` (Windows).

#### Frontend (production build)

```bash
cd frontend
npm run build
```

Output build berada di `frontend/dist/`. Sajikan direktori ini menggunakan web server statis.

**Penting untuk SPA routing:** Konfigurasi web server agar semua route di-redirect ke `index.html`:

```nginx
# Nginx
location / {
  try_files $uri $uri/ /index.html;
}
```

**Caching strategy:**
- `index.html` — `Cache-Control: no-cache, no-store, must-revalidate`
- `assets/*.js`, `assets/*.css` — `Cache-Control: public, max-age=31536000, immutable`

Testing production build lokal:
```bash
npx vite preview
# atau
npx serve frontend/dist -p 3000
```

---

## Verifikasi Instalasi

Setelah backend berjalan, verifikasi dengan:

### 1. Health check

```bash
curl http://localhost:8000/health
```

Response yang diharapkan:
```json
{"status": "ok"}
```

### 2. Cek API docs

Buka di browser: **http://localhost:8000/docs**

Ini adalah Swagger UI yang menampilkan semua REST endpoint.

### 3. Cek frontend

Buka **http://localhost:5173** — halaman Accounts harus tampil.

### 4. Cek koneksi frontend-backend

Di halaman Accounts, coba tambah akun Instagram. Jika muncul error "Cannot connect to backend", periksa:
- Backend berjalan di port yang sesuai
- `VITE_DEV_PROXY_TARGET` di `frontend/.env` mengarah ke backend

---

## Fitur & Konfigurasi Lanjutan

### Operator Copilot

AI assistant untuk manajemen multi-akun Instagram melalui chat interface.

```env
ENABLE_OPERATOR_COPILOT=1    # Aktifkan fitur
OPENAI_API_KEY=sk-...         # Minimal satu AI provider
```

Akses: Sidebar > **Copilot**

### Smart Engagement

Workflow otomatis untuk engagement (follow, comment, DM) dengan approval gate.

```env
SMART_ENGAGEMENT_EXECUTION_ENABLED=false   # false = recommendation only (aman)
                                           # true = bisa execute setelah approval
```

Akses: Sidebar > **Engagement**

### Relationships (Follow/Unfollow)

Halaman khusus untuk bulk follow/unfollow dan cross-follow antar managed accounts.

Tidak memerlukan konfigurasi tambahan. Fitur ini tersedia saat backend berjalan.

Akses: Sidebar > **Relationships**

### LangGraph Checkpointer

Untuk menyimpan state copilot/engagement antar restart:

```env
LANGGRAPH_CHECKPOINTER_BACKEND=sqlite
LANGGRAPH_CHECKPOINTER_SQLITE_PATH=sessions/langgraph_checkpoints.sqlite3
```

Dengan `memory` (default), state hilang saat backend restart. Gunakan `sqlite` untuk production.

---

## Keamanan & Akses

### Dashboard Login (Opsional)

Lindungi akses frontend dengan halaman login berbasis password. Setelah login berhasil, frontend menyimpan JWT Bearer token dan menyertakannya di setiap request API.

```env
ENABLE_DASHBOARD_AUTH=true
ADMIN_PASSWORD=password-kuat-anda
AUTH_SECRET=random-secret-panjang-untuk-jwt
```

Token berlaku **24 jam**. Setelah expired, frontend akan redirect otomatis ke `/login`.

Generate `AUTH_SECRET`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Catatan:** `ADMIN_PASSWORD` dan `AUTH_SECRET` harus berbeda. Jika salah satu kosong, fitur auth tidak akan aktif meskipun `ENABLE_DASHBOARD_AUTH=true`.

Endpoint yang **tidak** memerlukan auth: `/health`, `/docs`, `/openapi.json`, `/redoc`, `/api/dashboard/auth/status`, `/api/dashboard/auth/login`.

---

### API Key Backend (Opsional)

Tambahkan lapisan keamanan tambahan pada semua API endpoint. Frontend mengirimkan key ini via header `X-API-Key` pada setiap request.

**Backend** — tambahkan ke `backend/.env`:
```env
API_KEY=api-key-backend-anda
```

**Frontend** — konfigurasi dari halaman **Settings > Connection**:
- Masukkan API key yang sama di kolom **API Key**
- Klik **Save Settings**

Key disimpan di `localStorage` browser dan dikirim otomatis di semua request.

Endpoint yang **tidak** memerlukan API key: `/health`, `/docs`, `/openapi.json`, `/redoc`, `/api/dashboard/auth/status`, `/api/dashboard/auth/login`.

> **Kombinasi keduanya:** Jika `ENABLE_DASHBOARD_AUTH` dan `API_KEY` keduanya aktif, setiap request harus menyertakan:
> - `X-API-Key: <nilai>` — untuk autentikasi backend
> - `Authorization: Bearer <jwt>` — untuk sesi dashboard

---

### CORS untuk Production

Jika frontend dan backend berada di domain berbeda, konfigurasi CORS:

```env
APP_CORS_ORIGINS=https://dashboard.yourdomain.com
APP_CORS_ALLOW_HEADERS=Authorization,Content-Type,Accept,X-Requested-With,X-API-Key
```

> Header `X-API-Key` harus masuk ke `APP_CORS_ALLOW_HEADERS` agar browser mengizinkan request dengan API key dari domain berbeda.

---

## Troubleshooting

### Backend

**`ModuleNotFoundError` saat menjalankan uvicorn**
- Pastikan virtual environment sudah diaktifkan
- Jalankan ulang `pip install -r requirements.txt`

**`ENCRYPTION_KEY` error saat menggunakan persistence SQL/sqlite**
- Generate kunci baru:
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- Isi nilai tersebut ke `ENCRYPTION_KEY` di `.env`

**Port 8000 sudah digunakan**
- Ganti port: `--port 8001` pada perintah uvicorn
- Update `VITE_DEV_PROXY_TARGET=http://127.0.0.1:8001` di `frontend/.env`

**CORS error di browser**
- Pastikan `APP_CORS_ORIGINS` di `backend/.env` memuat URL frontend
- Contoh: `APP_CORS_ORIGINS=http://localhost:5173,http://localhost:3000`

**Instagram login gagal / challenge required**
- Beberapa akun memerlukan 2FA — setup TOTP dari halaman Accounts
- Gunakan proxy untuk menghindari rate limiting
- Cek apakah IP terblokir oleh Instagram

**Copilot tidak merespon / error**
- Pastikan minimal satu `*_API_KEY` terisi di `.env`
- Cek log backend untuk error detail
- Coba ganti provider di Settings

### Frontend

**`npm install` gagal**
- Pastikan versi Node.js minimal 20:
  ```bash
  node --version
  ```
- Hapus cache dan coba ulang:
  ```bash
  rm -rf node_modules package-lock.json
  npm install
  ```

**Halaman blank setelah `npm run dev`**
- Pastikan backend sudah berjalan
- Cek `VITE_DEV_PROXY_TARGET` di `frontend/.env`
- Buka browser console untuk error detail

**TypeScript error saat build**
- Jalankan type check: `npx tsc --noEmit`
- Fix error yang dilaporkan sebelum build

**Production build 404 pada refresh**
- Pastikan web server dikonfigurasi untuk SPA routing (lihat [Production Build](#production-build))

### Keamanan

**401 Unauthorized pada semua request API**
- Pastikan `API_KEY` di `backend/.env` sama persis dengan nilai yang dikonfigurasi di Settings > Connection frontend
- Cek apakah `APP_CORS_ALLOW_HEADERS` menyertakan `X-API-Key`

**Login dashboard gagal / "Invalid password"**
- Pastikan `ENABLE_DASHBOARD_AUTH=true`, `ADMIN_PASSWORD`, dan `AUTH_SECRET` semuanya terisi di `.env`
- Restart backend setelah mengubah env vars
- Jika token expired, logout lalu login ulang dari halaman `/login`

**Frontend redirect loop ke `/login`**
- Token JWT mungkin sudah expired (24 jam) — login ulang
- Pastikan backend dapat diakses dari browser (periksa URL di Settings)

### Database

**Alembic migration error**
```bash
cd backend
source .venv/bin/activate
alembic current        # Cek status
alembic upgrade head   # Coba upgrade manual
```

**SQLite locked**
- Hanya satu proses yang bisa menulis ke SQLite pada satu waktu
- Untuk multi-worker, gunakan PostgreSQL

---

> Untuk pertanyaan lebih lanjut, buka [issue](../../issues) di repositori ini.
