# Panduan Docker — InstaManager

Panduan ini menjelaskan cara menjalankan InstaManager menggunakan **Docker Compose** di **Windows 11** dan **Linux (Ubuntu)**.

Docker Compose akan menjalankan 3 service sekaligus:
- **PostgreSQL** — database persisten (internal only, tidak expose ke public)
- **Backend** — FastAPI API server (internal only, tidak expose ke public)
- **Frontend** — React SPA + reverse proxy via Nginx (**satu-satunya port yang terbuka ke public**)

### Arsitektur jaringan

```
Internet / Public IP
        │
        ▼
  :${FRONTEND_PORT}  ← hanya port ini yang terbuka
  ┌─────────────────────────────────┐
  │  Nginx (frontend container)     │
  │                                 │
  │  /api/*  ──────────────────────►  backend:8000 (internal)
  │  /health ──────────────────────►  backend:8000 (internal)
  │  /assets/* → static files       │
  │  /*        → index.html (SPA)   │
  └─────────────────────────────────┘
                    │ Docker internal network
                    ▼
             ┌──────────────┐
             │   Backend    │  ← tidak ada port publik
             │  (FastAPI)   │
             └──────┬───────┘
                    │
                    ▼
             ┌──────────────┐
             │  PostgreSQL  │  ← tidak ada port publik
             └──────────────┘
```

Backend dan database tidak memiliki port publik. Semua request dari browser diteruskan melalui nginx secara internal di Docker network.

---

## Daftar Isi

1. [Prasyarat](#prasyarat)
   - [Windows 11](#prasyarat--windows-11)
   - [Linux (Ubuntu)](#prasyarat--linux-ubuntu)
2. [Konfigurasi](#konfigurasi)
3. [Menjalankan](#menjalankan)
4. [Verifikasi](#verifikasi)
5. [Perintah Umum](#perintah-umum)
6. [pgAdmin (Opsional)](#pgadmin-opsional)
7. [Volume & Data](#volume--data)
8. [Update & Rebuild](#update--rebuild)
9. [Konfigurasi Port](#konfigurasi-port)
10. [Troubleshooting](#troubleshooting)

---

## Prasyarat

### Prasyarat — Windows 11

#### 1. Aktifkan WSL 2

Buka **PowerShell sebagai Administrator** dan jalankan:

```powershell
wsl --install
```

Restart komputer jika diminta. Setelah restart, verifikasi:

```powershell
wsl --version
```

> **Catatan:** Windows 11 (build 22000+) sudah menyertakan WSL 2 secara built-in.

#### 2. Pastikan Virtualization Aktif

Docker memerlukan virtualization (VT-x / AMD-V) yang harus diaktifkan di BIOS/UEFI.

Cek status di PowerShell:
```powershell
systeminfo | findstr "Hyper-V"
```

Jika tertulis `Hyper-V Requirements: A hypervisor has been detected`, virtualization sudah aktif.

Jika belum aktif:
1. Restart komputer, masuk BIOS/UEFI (biasanya tekan F2, F12, atau Del saat boot)
2. Cari opsi **Intel VT-x** atau **AMD SVM** dan aktifkan
3. Simpan dan restart

#### 3. Install Docker Desktop

Download dari [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) dan jalankan installer.

Atau via winget:
```powershell
winget install Docker.DockerDesktop
```

Setelah install:
1. Buka **Docker Desktop**
2. Buka **Settings** > **General**
3. Pastikan **Use the WSL 2 based engine** tercentang
4. Klik **Apply & Restart**

#### 4. Verifikasi

Buka **PowerShell** (tidak perlu Administrator):

```powershell
docker --version
docker compose version
```

Contoh output:
```
Docker version 27.x.x, build xxxxx
Docker Compose version v2.x.x
```

#### Kebutuhan Sistem

| Komponen | Minimum |
|----------|---------|
| OS | Windows 11 build 22000+ |
| RAM | 8 GB (16 GB direkomendasikan) |
| Disk | 3 GB untuk Docker images |
| CPU | Virtualization (VT-x/AMD-V) harus aktif |

---

### Prasyarat — Linux (Ubuntu)

#### 1. Install Docker Engine

```bash
# Hapus versi lama (jika ada)
sudo apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null

# Tambah repository resmi Docker
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

#### 2. Jalankan Docker tanpa sudo

```bash
sudo usermod -aG docker $USER
```

**Logout dan login kembali** agar perubahan group berlaku.

#### 3. Verifikasi

```bash
docker --version
docker compose version
```

#### Kebutuhan Sistem

| Komponen | Minimum |
|----------|---------|
| OS | Ubuntu 22.04+ / Debian 12+ |
| RAM | 4 GB (8 GB direkomendasikan) |
| Disk | 3 GB untuk Docker images |

---

## Konfigurasi

### 1. Salin file environment

**Linux:**
```bash
cd insta
cp .env.example .env
cp backend/.env.example backend/.env
```

**Windows (PowerShell):**
```powershell
cd insta
copy .env.example .env
copy backend\.env.example backend\.env
```

### 2. Edit `backend/.env`

Buka `backend/.env` dengan text editor dan isi minimal konfigurasi berikut:

```env
# Minimal: satu AI provider untuk Copilot
OPENAI_API_KEY=sk-proj-...

# Encryption key (wajib untuk mode SQL/PostgreSQL)
# Generate dengan: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=
```

> **Catatan:** Variabel `PERSISTENCE_BACKEND` dan `PERSISTENCE_DATABASE_URL` tidak perlu diisi — Docker Compose sudah mengatur koneksi ke PostgreSQL secara otomatis melalui environment override di `docker-compose.yml`.

### 3. (Opsional) Edit `.env` di root

File `.env` di root mengatur port dan password Docker:

```env
# Ubah jika port default sudah dipakai
BACKEND_PORT=8000
FRONTEND_PORT=3000
POSTGRES_PORT=5432

# Password PostgreSQL
POSTGRES_PASSWORD=instapass
```

---

## Menjalankan

### Start semua service

**Linux:**
```bash
docker compose up -d
```

**Windows (PowerShell):**
```powershell
docker compose up -d
```

Docker akan:
1. Build image backend (Python 3.12 + dependencies)
2. Build image frontend (Node 20 + Vite build + Nginx)
3. Pull image PostgreSQL 16
4. Start ketiga container

> **Pertama kali** akan memakan waktu 2-5 menit untuk build. Setelah itu, start cukup beberapa detik.

### Lihat log

```bash
# Semua service
docker compose logs -f

# Backend saja
docker compose logs -f backend

# Frontend saja
docker compose logs -f frontend
```

### Stop semua service

```bash
docker compose down
```

> Data PostgreSQL, session Instagram, dan checkpoint LangGraph **tetap tersimpan** di Docker volumes. Lihat bagian [Volume & Data](#volume--data).

---

## Verifikasi

Setelah `docker compose up -d`, verifikasi setiap service:

### 1. Cek status container

```bash
docker compose ps
```

Semua service harus menunjukkan status `Up` atau `running`:

```
NAME                SERVICE     STATUS
insta-postgres-1    postgres    Up (healthy)
insta-backend-1     backend     Up
insta-frontend-1    frontend    Up
```

### 2. Health check backend (via nginx proxy)

Backend tidak punya port publik, tetapi nginx meneruskan `/health` secara internal:

```bash
curl http://localhost:3000/health
```

Response:
```json
{"status": "ok"}
```

Atau langsung dari dalam container backend:
```bash
docker compose exec backend curl -s http://localhost:8000/health
```

### 3. Buka Swagger API docs

Swagger diakses melalui nginx proxy:

Buka di browser: **http://localhost:3000/api/docs** (jika diaktifkan)

Atau langsung dari dalam container (untuk debugging saja):
```bash
docker compose exec backend curl -s http://localhost:8000/docs | head -5
```

### 4. Buka frontend

Buka di browser: **http://localhost:3000**

Halaman **Accounts** harus tampil dengan UI Tokyo Night (dark theme).

### 5. Cek koneksi database

```bash
docker compose exec postgres psql -U instauser -d instamanager -c "SELECT 1;"
```

---

## Perintah Umum

| Perintah | Keterangan |
|----------|------------|
| `docker compose up -d` | Start semua service di background |
| `docker compose down` | Stop semua service (data tetap tersimpan) |
| `docker compose down -v` | Stop + hapus semua data (volumes) |
| `docker compose logs -f` | Lihat log realtime semua service |
| `docker compose logs -f backend` | Log backend saja |
| `docker compose ps` | Status semua container |
| `docker compose restart backend` | Restart backend saja |
| `docker compose exec backend bash` | Shell ke dalam container backend |
| `docker compose exec postgres psql -U instauser -d instamanager` | Masuk ke PostgreSQL CLI |

---

## pgAdmin (Opsional)

pgAdmin adalah web UI untuk mengelola database PostgreSQL. Aktifkan dengan profile `dev`:

```bash
docker compose --profile dev up -d
```

Akses: **http://localhost:5050**

Login:
- Email: `admin@local.dev`
- Password: `admin` (atau sesuai `PGADMIN_PASSWORD` di `.env`)

Untuk koneksi ke database:
- Host: `postgres`
- Port: `5432`
- Database: `instamanager`
- Username: `instauser`
- Password: sesuai `POSTGRES_PASSWORD` di `.env`

---

## Volume & Data

Docker Compose menggunakan **named volumes** untuk menyimpan data secara persisten:

| Volume | Isi | Lokasi di Container |
|--------|-----|-------------------|
| `insta-pg-data` | Database PostgreSQL | `/var/lib/postgresql/data` |
| `insta-sessions` | File session Instagram (instagrapi) | `/app/sessions` |
| `insta-checkpoints` | LangGraph checkpoint SQLite | `/app/checkpoints` |

### Data bertahan saat

- `docker compose down` (stop tanpa `-v`)
- `docker compose restart`
- Rebuild image (`docker compose up -d --build`)

### Data hilang saat

- `docker compose down -v` (flag `-v` menghapus volumes)
- `docker volume rm insta-pg-data` (hapus volume spesifik)

### Backup database

```bash
# Export
docker compose exec postgres pg_dump -U instauser instamanager > backup.sql

# Restore
docker compose exec -T postgres psql -U instauser instamanager < backup.sql
```

### Lihat ukuran volumes

```bash
docker system df -v | grep insta
```

---

## Update & Rebuild

Setelah pull perubahan kode atau update dependencies:

```bash
# Rebuild dan restart
docker compose up -d --build

# Atau rebuild service tertentu
docker compose build backend
docker compose up -d backend
```

### Rebuild tanpa cache (jika dependencies berubah)

```bash
docker compose build --no-cache
docker compose up -d
```

### Update image dasar (PostgreSQL, Nginx)

```bash
docker compose pull
docker compose up -d
```

---

## Konfigurasi Port

Hanya **satu port** yang perlu diatur untuk akses publik: port frontend.

Buat file `.env` di root project jika belum ada:

```env
# Satu-satunya port yang terbuka ke publik
FRONTEND_PORT=3000     # default: 3000

# Password PostgreSQL (internal)
POSTGRES_PASSWORD=instapass
```

`BACKEND_PORT` dan `POSTGRES_PORT` **tidak diperlukan** karena kedua service ini tidak expose port ke host.

Lalu restart:

```bash
docker compose down
docker compose up -d
```

> **Catatan:** Mengubah `FRONTEND_PORT` tidak memerlukan rebuild image — hanya port binding yang berubah.

---

## Troubleshooting

### Container tidak start / terus restart

```bash
# Lihat log untuk error detail
docker compose logs backend
docker compose logs postgres
```

### `port is already allocated`

Hanya port frontend (`:3000`) yang bisa konflik. Solusi:

```bash
# Cek apa yang pakai port 3000
# Linux:
sudo lsof -i :3000
# Windows (PowerShell):
netstat -ano | findstr :3000
```

Ganti port frontend di `.env`:
```env
FRONTEND_PORT=3001
```
Lalu `docker compose down && docker compose up -d`.

### Backend error: `ENCRYPTION_KEY`

Backend memerlukan encryption key untuk mode PostgreSQL. Generate dan tambahkan ke `backend/.env`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Atau di dalam container:
```bash
docker compose exec backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Backend tidak bisa konek ke PostgreSQL

Pastikan container postgres sudah healthy:
```bash
docker compose ps postgres
```

Jika status bukan `Up (healthy)`, cek log:
```bash
docker compose logs postgres
```

### Frontend blank / error `Cannot connect to backend`

1. Pastikan backend sudah running (via nginx proxy):
   ```bash
   curl http://localhost:3000/health
   ```
2. Cek log nginx untuk error proxy:
   ```bash
   docker compose logs frontend
   ```
3. Cek apakah backend container berjalan:
   ```bash
   docker compose exec backend curl -s http://localhost:8000/health
   ```
4. Jika ada error `502 Bad Gateway`, berarti backend belum siap — tunggu beberapa detik dan coba lagi.

### Akses backend langsung (untuk debugging saja)

Backend tidak expose port ke host. Untuk debug langsung, gunakan exec:

```bash
# Masuk ke shell backend
docker compose exec backend bash

# Atau jalankan perintah langsung
docker compose exec backend curl http://localhost:8000/api/accounts/
```

### Build lambat / gagal

```bash
# Bersihkan Docker cache
docker builder prune

# Rebuild dari awal
docker compose build --no-cache
```

### Permission denied (Linux)

Pastikan user sudah masuk group docker:
```bash
sudo usermod -aG docker $USER
# Logout dan login kembali
```

### Reset total (hapus semua data)

```bash
docker compose down -v
docker compose up -d
```

> **Peringatan:** Perintah ini menghapus semua data termasuk database, session Instagram, dan checkpoint AI.

---

## Arsitektur Docker

```
┌──────────────────────────────────────────────────────────────┐
│  Host (Windows 11 / Ubuntu)                                  │
│                                                              │
│  ┌─────────────────────────┐                                 │
│  │  Frontend (Nginx) :3000 │◄── Internet (satu-satunya port) │
│  │                         │                                 │
│  │  /api/* ──────────────► │ ──► backend:8000 (internal)     │
│  │  /health ─────────────► │ ──► backend:8000 (internal)     │
│  │  /* → React SPA         │                                 │
│  └─────────────────────────┘                                 │
│                   │ Docker internal network                   │
│                   ▼                                          │
│  ┌────────────────────┐    ┌────────────────────┐           │
│  │  Backend (Uvicorn) │    │    PostgreSQL       │           │
│  │  port: internal    │───▶│    port: internal   │           │
│  └────────────────────┘    └────────────────────┘           │
│         │                        │                           │
│    ┌────┴────┐              ┌────┴────┐                      │
│    │sessions │              │ pg-data │                      │
│    │checkpts │              │(volume) │                      │
│    │(volumes)│              └─────────┘                      │
│    └─────────┘                                               │
└──────────────────────────────────────────────────────────────┘

Browser ──▶ :3000 (Nginx)
                   │
                   ├── /api/*     → proxy ke backend:8000
                   ├── /health    → proxy ke backend:8000
                   ├── /assets/*  → static files (immutable cache)
                   └── /*         → index.html (SPA routing)
```

---

> Untuk instalasi **tanpa Docker** (langsung di host), lihat [INSTALLATION.md](./INSTALLATION.md).
