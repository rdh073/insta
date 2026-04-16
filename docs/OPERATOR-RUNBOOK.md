# Runbook Operator — InstaManager

Panduan operasional untuk menjalankan fitur-fitur InstaManager dari sisi frontend.
Dokumen ini ditujukan untuk operator yang mengelola banyak akun Instagram melalui dashboard.

---

## Daftar Isi

1. [Manajemen Akun](#1-manajemen-akun)
2. [Settings & AI Provider](#2-settings--ai-provider)
3. [OAuth Setup (Codex & Claude)](#3-oauth-setup-codex--claude)
4. [Operator Copilot](#4-operator-copilot)
5. [Smart Engagement](#5-smart-engagement)
6. [Relationships (Follow/Unfollow)](#6-relationships-followunfollow)
7. [Proxy Management](#7-proxy-management)
8. [Catatan Penting & Tips](#8-catatan-penting--tips)
9. [Penanganan Error Umum](#9-penanganan-error-umum)

---

## 1. Manajemen Akun

**Lokasi:** Sidebar > **Accounts**

### Menambah Akun

1. Klik tombol **Add Account** (pojok kanan atas)
2. Isi form:
   - **Username** — username Instagram (tanpa @)
   - **Password** — password Instagram
   - **Proxy** (opsional) — format `http://user:pass@host:port` atau `socks5://host:port`
   - **2FA Secret** (opsional) — kode base32 dari authenticator app
3. Klik **Login**
4. Jika akun menggunakan 2FA, akan muncul form kedua:
   - Masukkan **kode 6 digit** dari authenticator app atau SMS
   - Klik **Verify**

### Import Akun Massal

1. Klik **Import File**
2. Drop file `.txt` / `.csv` atau paste langsung ke textarea
3. Format per baris:
   ```
   username:password
   username:password:http://proxy:port
   username:password:proxy|totp_secret
   ```
4. Klik **Import**

### Status Akun

| Status | Warna | Arti |
|--------|-------|------|
| **Active** | Hijau | Siap digunakan untuk semua operasi |
| **Idle** | Abu-abu | Belum login / session belum dimuat |
| **Logging in** | Biru | Sedang proses login |
| **Error** | Merah | Login gagal atau session expired |
| **Challenge** | Kuning | Instagram meminta verifikasi tambahan |
| **Challenge Pending** | Kuning | Menunggu operator memasukkan 6-digit challenge code |
| **2FA Required** | Kuning | Menunggu kode 2FA |

### Aksi per Akun

- **Activate** (tombol hijau) — Re-login akun yang idle atau error
- **Setup 2FA** (ikon gembok) — Generate TOTP secret + scan QR code
- **Logout** (ikon sampah merah) — Hapus akun dari sistem

### Aksi Massal (Select Mode)

1. Klik **Select** di toolbar
2. Pilih akun menggunakan checkbox, atau gunakan chip:
   - **Select all** — pilih semua akun
   - **Select all errors** — pilih akun bermasalah
   - **Clear** — batalkan semua
3. Gunakan action bar di bawah:
   - **Relogin All** — login ulang semua yang dipilih
   - **Set Proxy** — atur proxy untuk semua yang dipilih
   - **Logout All** — hapus semua yang dipilih

### Setup 2FA (TOTP)

1. Klik ikon **gembok** pada akun yang aktif
2. Klik **Generate TOTP Secret**
3. Scan QR code dengan authenticator app (Google Authenticator, Authy, dll.)
4. Atau salin **manual secret** (teks biru di bawah QR)
5. Masukkan kode 6 digit pertama dari authenticator
6. Klik **Verify & Enable**

> **Catatan:** Setelah 2FA aktif, sistem akan otomatis generate kode saat login ulang jika secret tersimpan.

### Resolving a Challenge (Email/SMS Code)

Saat Instagram meminta kode 6-digit lewat email atau SMS, login masuk ke
status **Challenge Pending**. Thread login backend akan menunggu kode
selama `CHALLENGE_WAIT_TIMEOUT_SECONDS` detik (default 600 detik / 10 menit)
sebelum gagal.

**Alur resolusi:**

1. Operator memicu login. Backend menerima challenge Instagram dan
   mempublikasikan entry pending.
2. Frontend (atau operator via curl) memanggil
   `GET /api/accounts/challenges/pending` — menampilkan daftar akun yang
   menunggu kode, beserta metode (`EMAIL` / `SMS`) dan `contact_hint`.
3. Operator membaca kode 6-digit dari inbox/ponsel dan submit via
   `POST /api/accounts/{account_id}/challenge/submit` dengan body
   `{"code": "123456"}`. Response berisi `status="resolved"`.
4. Thread login yang tertunda melanjutkan dan akun menjadi `active`.

**Endpoint tambahan:**

- `GET /api/accounts/{id}/challenge` — 200 dengan payload pending,
  204 bila tidak ada challenge yang tertunda.
- `DELETE /api/accounts/{id}/challenge` — batalkan challenge pending
  sehingga `login()` yang terblokir segera raise dan kembali ke status
  error.

> **Catatan:** Resolver hidup di memori proses. Restart backend akan
> membatalkan challenge yang sedang tertunda — operator harus memicu
> login ulang.

---

## 2. Settings & AI Provider

**Lokasi:** Sidebar > **Settings**

### Backend Connection

- Kolom **Backend URL** menentukan alamat API server
- Default: `http://localhost:8000`
- Untuk production: isi URL server backend yang sebenarnya
- Klik **Save Settings** setelah mengubah

### Memilih AI Provider

1. Di bagian **AI Routing**, pilih provider dari tab yang tersedia
2. Provider yang tersedia:
   - **OpenAI** — masukkan API key (`sk-...`)
   - **Gemini** — masukkan API key (`AIza...`)
   - **DeepSeek** — masukkan API key
   - **Antigravity** — proxy lokal untuk model lokal
   - **OpenAI Codex** — OAuth (lihat bagian 3)
   - **Claude Code** — OAuth (lihat bagian 3)
3. Masukkan API key di kolom password
4. Pilih model dari dropdown (atau ketik nama model custom)
5. Klik **Save Settings**

### Kapan Ganti Provider

| Situasi | Provider yang Disarankan |
|---------|------------------------|
| Tugas umum (baca data, analisa) | OpenAI GPT-4o atau Gemini Flash |
| Tugas menulis (caption, komentar) | OpenAI GPT-4o |
| Budget terbatas | DeepSeek |
| Model lokal / self-hosted | Antigravity |
| Akses via OAuth organisasi | Codex atau Claude Code |

> **Penting:** API key disimpan di browser (localStorage). Jika membuka dari browser/device lain, perlu diisi ulang.

---

## 3. OAuth Setup (Codex & Claude)

OAuth digunakan untuk provider yang menggunakan autentikasi organisasi, bukan API key biasa.

### Setup OpenAI Codex

1. Di Settings > AI Routing, pilih tab **OpenAI Codex**
2. Klik tombol **Connect OpenAI Codex OAuth**
3. Browser akan membuka halaman login OpenAI
4. Login dengan akun OpenAI yang memiliki akses Codex
5. Setelah login, browser akan redirect ke `localhost:1455`
   - **Halaman "Connection Refused" adalah normal** — ini bukan error
6. Salin **seluruh URL** dari address bar browser
   - Contoh: `http://localhost:1455/callback?code=xxx&state=yyy`
7. Kembali ke InstaManager, paste URL tersebut di kolom yang muncul
8. Klik **Exchange Code**
9. Jika berhasil, akan muncul notifikasi hijau dan provider langsung aktif

### Setup Claude Code

1. Di Settings > AI Routing, pilih tab **Claude Code**
2. Klik tombol **Connect Claude Code OAuth**
3. Browser akan membuka halaman otorisasi Anthropic
4. Login dan setujui akses
5. Halaman Anthropic akan menampilkan sebuah **kode**
6. Salin kode tersebut
7. Kembali ke InstaManager, paste kode di kolom yang muncul
8. Klik **Exchange Code**

### Troubleshooting OAuth

| Masalah | Solusi |
|---------|--------|
| "Connection Refused" setelah login Codex | Ini **normal** — salin URL dari address bar |
| Kode expired | Ulangi proses dari awal — kode berlaku singkat |
| Exchange gagal | Pastikan backend berjalan dan `.env` memiliki konfigurasi OAuth yang benar |
| Token expired setelah beberapa waktu | Refresh token otomatis — jika gagal, ulangi koneksi |

### Variabel Backend untuk OAuth

Pastikan variabel berikut terisi di `backend/.env` jika menggunakan OAuth:

```env
# OpenAI Codex
ENABLE_PROVIDER_OPENAI_CODEX=true
OPENAI_CODEX_ACCESS_TOKEN=    # diisi otomatis setelah exchange
OPENAI_CODEX_REFRESH_TOKEN=   # diisi otomatis setelah exchange

# Claude Code
ENABLE_PROVIDER_CLAUDE_CODE=true
CLAUDE_CODE_ACCESS_TOKEN=     # diisi otomatis setelah exchange
CLAUDE_CODE_REFRESH_TOKEN=    # diisi otomatis setelah exchange
```

> **Catatan:** Setelah exchange berhasil dari UI, token disimpan di backend dan di-refresh otomatis. Operator tidak perlu mengisi token manual.

---

## 4. Operator Copilot

**Lokasi:** Sidebar > **Copilot**

Copilot adalah AI assistant yang bisa menjalankan tool Instagram melalui percakapan natural language.

### Cara Menggunakan

1. Ketik perintah di kolom input bawah
2. Tekan **Enter** untuk kirim (Shift+Enter untuk baris baru)
3. Copilot akan:
   - Mengklasifikasi intent (tujuan) pesan
   - Membuat rencana eksekusi (tool apa yang dipanggil)
   - Mengevaluasi risiko (read-only atau write-sensitive)
   - Meminta approval jika ada aksi write
   - Menjalankan tool dan menampilkan hasil
   - Merangkum jawaban dalam bahasa yang sama dengan input

### Contoh Perintah

| Perintah | Apa yang Terjadi |
|----------|-----------------|
| `List all active accounts and their status` | Menampilkan daftar akun dengan followers, status, proxy |
| `Show recent engagement activity for the last 7 days` | Menampilkan statistik engagement |
| `Check proxy health and report any issues` | Tes semua proxy dan laporkan yang mati |
| `Follow @targetuser from @myaccount` | **Meminta approval dulu**, lalu follow |
| `Send DM "hello" to @someone from @myaccount` | **Meminta approval dulu**, lalu kirim DM |
| `Berapa follower @myaccount?` | Bisa dalam Bahasa Indonesia — respon juga dalam BI |

### Menggunakan @mention

- Ketik `@` di input untuk memunculkan daftar akun
- Pilih akun dengan panah atas/bawah lalu Enter
- Contoh: `Show followers of @alice using @bob`
  - `@bob` = akun managed yang melakukan API call
  - `@alice` = target yang dilihat

### Approval Flow

Ketika Copilot merencanakan aksi **write-sensitive** (follow, unfollow, DM, comment, dll.):

1. Muncul **card kuning** "Approval Required"
2. Card menampilkan:
   - Tool yang akan dipanggil
   - Argumen yang disiapkan
   - Alasan risiko
3. Pilih salah satu:
   - **Approve** (hijau) — jalankan sesuai rencana
   - **Reject** (merah) — batalkan, tidak ada aksi
   - **Edit** — modifikasi argumen sebelum jalankan

### Mengganti Provider di Copilot

- Klik dropdown provider di pojok kanan atas halaman Copilot
- Pilih provider dan model
- Perubahan langsung berlaku untuk pesan berikutnya

### Status Indicator

| Badge | Arti |
|-------|------|
| **idle** | Siap menerima input |
| **running** | Sedang memproses — input disabled |
| **waiting_approval** | Menunggu keputusan operator |
| **done** | Selesai |
| **error** | Terjadi error — cek pesan merah |

### Event yang Muncul di Chat

| Event | Ikon | Arti |
|-------|------|------|
| `run started` | Play | Session dimulai |
| Node name (italic) | Chevron | Graph sedang memproses node tertentu |
| `execution_plan` | Expand | Rencana tool yang akan dijalankan |
| `policy_check` | List | Hasil klasifikasi risiko |
| `tool_result` | Wrench | Hasil eksekusi tool |
| Final response | Bot | Jawaban akhir yang dirangkum |
| `run complete` | Stop | Session selesai |
| `run_error` | Alert | Error — baca pesan untuk detail |

---

## 5. Smart Engagement

**Lokasi:** Sidebar > **Engagement**

Smart Engagement menggunakan AI untuk merencanakan aksi engagement yang aman dan terukur.

### Cara Menggunakan

1. **Pilih Akun**
   - Klik dropdown "Accounts"
   - Pilih satu atau lebih akun aktif
   - Atau pilih "All Active Accounts"

2. **Tentukan Goal**
   - Pilih salah satu template cepat:
     - Like niche posts
     - Comment on follower posts
     - Engage with hashtags
     - Warm up cold leads
     - Reply to mentions
     - Support collaborators
   - Atau ketik goal custom di kolom input

3. **Pilih Mode**
   - **Recommendation** (default, aman) — AI hanya memberikan saran, tidak ada aksi nyata
   - **Execute** — AI akan menjalankan aksi setelah approval (harus diaktifkan di backend)

4. **Set Max Targets** — jumlah target maksimal yang dicari (1-20)

5. Klik **Run for N account(s)**

### Memahami Hasil

Setiap akun menghasilkan card terpisah yang berisi:

- **Recommendation** — target yang dipilih, jenis aksi, konten draft, alasan pemilihan
- **Risk Assessment** — level risiko (low/medium/high) dengan alasan
- **Outcome** — alasan kenapa workflow berhenti (recommendation_only, no_candidates, risk_threshold_exceeded, dll.)

### Approval (Mode Execute)

Jika mode **Execute** aktif dan AI menemukan target:

1. Akan muncul card dengan badge **"Awaiting approval"**
2. Review rekomendasi: target, aksi, konten draft, risiko
3. Pilih:
   - **Approve** — jalankan aksi
   - **Reject** — batalkan
   - **Edit** — ubah konten draft, lalu submit

### Mode Execute vs Recommendation

| | Recommendation | Execute |
|---|---|---|
| Aksi nyata dijalankan | Tidak | Ya (setelah approval) |
| Membutuhkan backend flag | Tidak | Ya (`SMART_ENGAGEMENT_EXECUTION_ENABLED=true`) |
| Cocok untuk | Review, planning, testing | Eksekusi langsung |
| Risiko | Nol | Tergantung aksi yang di-approve |

> **Peringatan:** Mode Execute menjalankan aksi nyata di Instagram (follow, comment, DM). Pastikan goal dan target sudah benar sebelum approve.

---

## 6. Relationships (Follow/Unfollow)

**Lokasi:** Sidebar > **Relationships**

Halaman ini untuk operasi bulk follow/unfollow dan cross-follow antar akun managed.

### Tab Follow

1. **Pilih akun** yang akan melakukan follow (bisa multi-select)
   - Klik akun satu per satu, atau **Select all**
2. **Ketik target usernames** di textarea
   - Pisahkan dengan enter, koma, atau titik koma
   - Contoh: `alice, bob, charlie` atau satu per baris
   - Prefix `@` otomatis dihapus
3. Preview chip akan muncul di bawah (max 8 ditampilkan)
4. Klik **Follow N users from M accounts**
5. Hasil ditampilkan realtime per-aksi (centang hijau / silang merah)

### Tab Unfollow

Sama persis dengan tab Follow, tetapi tombol berwarna merah dan menjalankan unfollow.

### Tab Cross-Follow

Fitur untuk membuat semua akun managed saling follow satu sama lain.

1. **Pilih 2+ akun** aktif
2. Klik **Check Relationships** — sistem mengecek siapa yang sudah saling follow
3. **Relationship Matrix** akan muncul:
   - Badge **hijau "follows"** = sudah follow
   - Badge **merah "not following"** = belum follow
   - Badge **loading** = sedang dicek
4. Jika ada yang belum saling follow, tombol **Follow Missing** muncul
5. Klik untuk menjalankan semua follow yang missing secara otomatis

> **Tips:** Cross-follow berguna untuk membuat jaringan akun terlihat natural dan saling terhubung.

---

## 7. Proxy Management

**Lokasi:** Sidebar > **Proxy**

### Tab Account Routing

Mengatur proxy per akun individual.

1. **Bulk Apply** (panel kiri):
   - Isi URL proxy
   - Klik **Test Proxy** untuk verifikasi sebelum apply
   - Pilih akun di daftar kanan (checkbox)
   - Klik **Apply Proxy** atau **Clear Proxy**

2. **Per Akun** (daftar kanan):
   - Klik **Edit route** / **Set route** per akun
   - Modal muncul dengan kolom proxy dan tombol test
   - Klik **Save Proxy** atau **Clear Proxy**

### Tab Proxy Pool

Mengelola kumpulan proxy yang sudah diverifikasi.

1. **Import**:
   - Paste daftar proxy atau browse file `.txt` / `.csv`
   - Format: `ip:port`, `proto:ip:port`, `proto://ip:port`
   - Klik **Import & Check** — sistem otomatis test dan simpan yang elite
   - Hasil import ditampilkan: saved, transparent (skip), duplicate, failed

2. **Single Check**:
   - Paste URL proxy dan klik **Check** untuk test manual

3. **Pool Management**:
   - Lihat semua proxy tersimpan dengan badge: protocol, anonymity, latency
   - **Recheck All** — test ulang semua proxy, hapus yang mati
   - **Delete** — hapus proxy individual

---

## 8. Catatan Penting & Tips

### Akun Idle / Error Berulang

> **PENTING:** Jika akun berstatus **idle** dan muncul **error berulang kali** saat mencoba relogin dari InstaManager, lakukan langkah berikut:
>
> 1. **Login manual** terlebih dahulu melalui browser di [instagram.com](https://www.instagram.com/)
> 2. Selesaikan semua tantangan keamanan yang diminta Instagram (captcha, verifikasi email/SMS, konfirmasi "ini saya")
> 3. Pastikan akun bisa diakses normal di browser
> 4. **Setelah itu**, baru kembali ke InstaManager dan klik **Activate** untuk relogin
>
> Instagram sering memblokir login dari API jika mendeteksi aktivitas tidak biasa. Login manual di browser "membersihkan" status akun di sisi Instagram sehingga login dari API bisa berhasil kembali.

### Tips Umum

- **Gunakan proxy berbeda per akun** — menghindari rate limiting karena banyak akun dari 1 IP
- **Jangan terlalu agresif** — batasi engagement ke 10-20 aksi per akun per hari
- **Monitor status akun** — cek halaman Accounts secara berkala untuk akun yang bermasalah
- **Backup session** — gunakan **Export Session** untuk backup sebelum perubahan besar
- **Gunakan mode Recommendation dulu** — sebelum mengaktifkan mode Execute di Smart Engagement, pastikan rekomendasi sudah sesuai harapan

### Batasan yang Perlu Dipahami

| Batasan | Detail |
|---------|--------|
| Rate limiting Instagram | Terlalu banyak aksi dalam waktu singkat bisa memicu challenge atau ban |
| Session expiry | Session Instagram bisa expire setelah beberapa hari — relogin diperlukan |
| 2FA timeout | Kode 2FA berlaku 30 detik — input harus cepat |
| API key localStorage | API key AI disimpan di browser — tidak tersinkron antar device |
| Copilot satu sesi | Copilot menggunakan thread terpisah per "New Chat" — konteks tidak carry over ke sesi baru (kecuali memory diaktifkan) |

### Keyboard Shortcuts (Copilot)

| Shortcut | Aksi |
|----------|------|
| `Enter` | Kirim pesan |
| `Shift + Enter` | Baris baru |
| `@` | Buka daftar akun |
| `/` | Buka daftar perintah |
| `Esc` | Tutup dropdown |
| `↑` `↓` | Navigasi dropdown |

---

## 9. Penanganan Error Umum

### Error pada Akun

| Error | Kemungkinan Penyebab | Solusi |
|-------|---------------------|--------|
| "Challenge required" | Instagram meminta verifikasi | Login manual di browser instagram.com, selesaikan challenge, lalu relogin di InstaManager |
| "Login failed" | Password salah atau akun diblokir | Cek password, login manual di browser dulu |
| "Two-factor authentication required" | 2FA aktif tapi secret belum disimpan | Setup 2FA di InstaManager atau input kode manual |
| "Proxy connection failed" | Proxy tidak bisa dijangkau | Test proxy di halaman Proxy, ganti jika mati |
| "Rate limited" | Terlalu banyak request | Tunggu 15-30 menit, kurangi intensitas |
| "Session expired" | Session sudah kedaluwarsa | Klik Activate untuk relogin |

### Error pada Copilot

| Error | Solusi |
|-------|--------|
| "run_error" muncul di chat | Baca pesan error — biasanya timeout atau tool gagal |
| Copilot tidak merespon | Cek apakah AI provider terkonfigurasi di Settings |
| "Unknown tool" di log | Tool yang diminta tidak tersedia — copilot akan menyesuaikan |
| Approval timeout | Copilot menunggu terlalu lama — reject dan coba lagi |
| Response dalam bahasa salah | Copilot merespon sesuai bahasa input — tulis dalam bahasa yang diinginkan |

### Error pada Smart Engagement

| Error | Solusi |
|-------|--------|
| "No active accounts" | Login minimal satu akun di halaman Accounts |
| "No candidates found" | Goal terlalu spesifik atau akun tidak punya data — coba goal berbeda |
| "Risk threshold exceeded" | AI menilai aksi terlalu berisiko — cek alasan di risk assessment |
| "Account not ready" | Akun belum login atau dalam cooldown — cek status di Accounts |
| "Execution mode not enabled" | Set `SMART_ENGAGEMENT_EXECUTION_ENABLED=true` di backend `.env` |

### Error pada Relationships

| Error | Solusi |
|-------|--------|
| "Follow failed" | Target mungkin memblokir akun, atau rate limited — tunggu dan coba lagi |
| "Account not found" | Username target salah — cek penulisan |
| Cross-follow "checking" terus | API lambat atau timeout — refresh halaman dan coba lagi |

---

> Untuk panduan instalasi, lihat [INSTALLATION.md](./INSTALLATION.md) atau [DOCKER-INSTALLATION.md](./DOCKER-INSTALLATION.md).
