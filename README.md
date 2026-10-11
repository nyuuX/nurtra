# Nurtra 🥗

Aplikasi penghitung kalori harian untuk program defisit kalori — dibuat untuk
pengguna Indonesia. Frontend vanilla JS + Tailwind-free CSS, backend Python
FastAPI, integrasi AI **Atria Dawn** (text-only).

> **Catatan Atria Dawn:** model ini berbasis teks saja. Semua permintaan ke
> `https://api.atria-asi.ai/v1` dikirim sebagai JSON / chat-completions.
> Jangan pernah mengirim gambar/biner ke endpoint ini.

## Fitur

1. **Kalkulator TDEE & target defisit dinamis** — Mifflin-St Jeor (atau
   Katch-McArdle bila body fat diisi), activity multiplier, safety caps
   (defisit maks 25% TDEE, floor kalori 1200/1500, maks 1 kg/minggu).
2. **Logging makanan** — database lokal 70+ bahan & menu Indonesia (dada ayam,
   tempe, nasi putih, nasi padang…), smart search, bottom sheet dengan portion
   slider & preset, **Quick Add** manual, favorit, dan parsing teks bebas via
   Atria Dawn ("nasi putih 1 mangkuk sama ayam geprek").
3. **Meal window & timer puasa intermiten** — 12:12 sampai 20:4, chip status
   di dashboard (makan sekarang / sedang puasa).
4. **Tracker protein & volume eating** — protein diprioritaskan (1.8 g/kg,
   floor 100 g), makanan high-volume/low-kcal diberi tag `VOLUME`.
5. **Log latihan & net calorie** — `(Kalori Masuk) − (Kalori Terbakar) =
   Sisa Kuota`; estimasi MET untuk 12 jenis olahraga.
6. **Laporan mingguan** — grafik batang 7 hari vs garis target, smooth spline
   tren berat badan (Catmull-Rom), adherence rate, rata-rata protein, dan
   insight + rekomendasi otomatis dari Atria Dawn (deteksi plateau, saran
   protein, volume eating, latihan).

## Stack

- **Frontend:** HTML5 + CSS (CSS variables, light/dark) + vanilla JS. Zero
  build step, zero npm dependency. Chart digambar dengan SVG manual.
- **Backend:** Python 3.14, FastAPI, uvicorn, httpx. Simpan data ke file JSON
  (`data/defisitku.json`) — gampak diganti Postgres nanti.
- **AI:** Atria Dawn (`Atria-Dawn-Preview`) lewat endpoint OpenAI-compatible.

## Menjalankan secara lokal

Butuh Python 3.11+ dan `uv` (atau `pip`).

```bash
# 1. Clone & masuk folder
git clone <repo-anda> defisitku
cd defisitku

# 2. Buat virtualenv & install dependensi
uv venv .venv --python 3.14
uv pip install --python .venv/Scripts/python.exe -r backend/requirements.txt
#   atau dengan pip:
#   python -m venv .venv
#   .venv/Scripts/activate        # Windows
#   source .venv/bin/activate     # macOS/Linux
#   pip install -r backend/requirements.txt

# 3. Konfigurasi
cp .env.example .env
#   edit .env, isi ATRIA_API_KEY
#   AI_MODE=atria  -> pakai Atria Dawn
#   AI_MODE=demo   -> fallback lokal (tanpa API key, tetap jalan)

# 4. Jalankan server (frontend + backend di satu port)
.venv/Scripts/python.exe -m uvicorn backend.app.app:app --reload --port 8000

# 5. Buka http://127.0.0.1:8000
```

Aplikasi langsung berisi data demo (profil + 6 hari log + berat badan) sehingga
dashboard dan laporan langsung terlihat isinya.

## Struktur proyek

```
defisitku/
├── .env.example              # template konfigurasi
├── .env                      # API key dsb. (jangan di-commit)
├── backend/
│   ├── requirements.txt
│   ├── tools/
│   │   └── backfill_exercise_ids.py   # migrasi data lama (lihat di bawah)
│   └── app/
│       ├── app.py            # FastAPI app + serve frontend + /api/health
│       ├── config.py         # baca .env (tanpa dependensi tambahan)
│       ├── store.py          # JSON store + seed data demo + migrasi schema
│       ├── users.py          # tabel user + hashing password (PBKDF2)
│       ├── sessions.py       # token sesi HMAC (httpOnly cookie)
│       ├── data_context.py   # resolver: request -> data slice user/anonim
│       ├── nutrition.py      # BMR/TDEE, macro, puasa, adherence, plateau
│       ├── foods.py          # 70+ makanan Indonesia + daftar latihan (MET)
│       ├── atria_client.py   # transport Atria Dawn (chat + JSON extractor)
│       ├── ai_parse.py       # fitur #2: teks bebas -> structured foods
│       ├── ai_insights.py    # fitur #6: insight & rekomendasi mingguan
│       ├── ai_recipes.py     # fitur #2/#4: resep tinggi protein
│       └── routers/
│           ├── core.py       # profile, foods, meals, exercises, weight, favs
│           ├── auth.py       # signup, login, logout, /me, migrasi anonim
│           ├── ai.py         # endpoint AI
│           └── report.py     # laporan mingguan
├── frontend/
│   └── static/
│       ├── index.html        # dashboard + bottom sheets (halaman utama)
│       ├── login.html        # halaman login/daftar
│       ├── profile.html      # halaman profil & target defisit
│       ├── report.html       # halaman laporan mingguan
│       ├── css/style.css     # tema light/dark, token warna
│       └── js/
│           ├── api.js        # client API
│           ├── charts.js     # SVG: bar chart + smooth spline berat badan
│           ├── app.js        # dashboard + shared helpers (NurtraShared)
│           ├── login.js      # logika halaman login
│           ├── profile.js    # logika halaman profil
│           └── report.js     # logika halaman laporan
└── data/
    └── defisitku.json        # dibuat otomatis saat first run
```

Halaman dipisah: dashboard (`/`), profil (`/profile.html`), dan laporan
(`/report.html`) adalah file HTML terpisah yang berbagi helper di `app.js`
lewat objek `window.NurtraShared`.


## API

| Method | Endpoint                      | Keterangan                              |
|--------|-------------------------------|------------------------------------------|
| GET    | `/api/health`                 | status + mode AI                         |
| GET    | `/api/profile`                | profil + BMR/TDEE/target/macro           |
| POST   | `/api/profile`                | simpan profil, hitung ulang target       |
| GET    | `/api/today`                  | ringkasan dashboard hari ini             |
| GET    | `/api/days/{date}`            | ringkasan tanggal tertentu               |
| POST   | `/api/auth/signup`            | daftar user baru                         |
| POST   | `/api/auth/login`             | masuk                                    |
| POST   | `/api/auth/logout`            | keluar                                   |
| GET    | `/api/auth/me`                | user saat ini (null = anonim)            |
| POST   | `/api/auth/migrate-anonymous` | adopsi data demo ke akun baru            |
| GET    | `/api/foods/search?q=`        | cari makanan                             |
| GET    | `/api/foods/volume`           | makanan high-volume low-kcal             |
| POST   | `/api/meals/{meal}`           | tambah entry makanan                     |
| DELETE | `/api/meals/{meal}/{id}`      | hapus entry                              |
| GET    | `/api/exercises`              | daftar latihan (MET)                     |
| POST   | `/api/exercises`              | log latihan                              |
| DELETE | `/api/exercises/{id}`         | hapus latihan                            |
| POST   | `/api/weight`                 | catat berat badan                        |
| GET    | `/api/favorites`              | menu favorit                             |
| POST   | `/api/favorites`              | simpan favorit                           |
| GET    | `/api/report?weeks_back=0`    | laporan mingguan                         |
| GET    | `/api/ai/status`              | mode AI (atria/demo)                     |
| POST   | `/api/ai/parse-foods`         | teks -> structured foods                 |
| POST   | `/api/ai/recipes`             | resep tinggi protein                     |
| POST   | `/api/ai/weekly-insights`     | insight mingguan                         |

Dokumentasi interaktif: `http://127.0.0.1:8000/docs`.

## Payload Atria Dawn

Lihat [`docs/atria-payloads.md`](docs/atria-payloads.md) untuk contoh request &
response lengkap dari ketiga fitur AI.

## Mode demo

Tanpa `ATRIA_API_KEY` (atau `AI_MODE=demo`), semua fitur AI memakai fallback
lokal deterministik — aplikasi tetap utuh, hanya insight-nya yang berasal dari
rule engine, bukan LLM.

## Akun & login

- Email + password, di-hash dengan PBKDF2-SHA256 (salt per-user, 200k iterasi).
- Sesi: cookie `dk_session` httpOnly berisi token HMAC yang ditandatangani
  secret server (TTL 30 hari). Secret dibuat otomatis di `data/.session_secret`.
- Tanpa login, aplikasi memakai data demo yang sama seperti biasa — tidak ada
  fitur yang terkunci.
- Data tiap user terpisah (meals, exercises, profile, favorites). Saat signup
  pertama, data demo anonim diadopsi ke akun baru via `/api/auth/migrate-anonymous`
  supaya tidak hilang.
- Login Google: tombolnya sudah ada di `/login.html` tapi masih placeholder —
  butuh OAuth credentials (Client ID + secret dari Google Cloud Console) untuk
  diaktifkan.

## Catatan: data lama tanpa id exercise

Versi awal menyimpan entri latihan tanpa field `id`, sehingga tombol hapus
olahraga selalu 404. Seed data sekarang mengisi `id`, dan backend sudah
mendukung fallback ke nama. Jika Anda punya file `data/defisitku.json` lama:

```bash
cd backend
../.venv/Scripts/python.exe -m tools.backfill_exercise_ids
```

Atau hapus saja `data/defisitku.json` — akan dibuat ulang dengan seed yang
benar saat server dinyalakan.

