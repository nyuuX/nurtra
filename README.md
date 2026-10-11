# Nurtra 

Aplikasi penghitung kalori harian untuk program defisit kalori — dibuat untuk
pengguna Indonesia. Frontend vanilla JS + Tailwind-free CSS, backend Python
FastAPI, integrasi AI **Atria Dawn**

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
