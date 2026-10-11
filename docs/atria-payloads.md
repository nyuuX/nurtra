# Contoh Payload Atria Dawn

Endpoint: `https://api.atria-asi.ai/v1/chat/completions`
Model: `Atria-Dawn-Preview` (**text-only** — tidak menerima gambar/biner)

Semua fitur AI memakai format OpenAI-compatible chat completions. Backend
membungkus data mentah sebagai JSON string di `user` message, dan meminta
output **hanya JSON** di `system` message.

---

## 1. Parse makanan dari teks bebas (fitur #2)

### Request

```json
POST /api/ai/parse-foods
{ "text": "nasi putih 1 mangkuk sama ayam geprek" }
```

Yang dikirim backend ke Atria:

```json
{
  "model": "Atria-Dawn-Preview",
  "temperature": 0.2,
  "messages": [
    {
      "role": "system",
      "content": "Kamu adalah asisten nutrisi untuk aplikasi Indonesia bernama Nurtra.\nTugas: ubah deskripsi makanan dalam bahasa Indonesia menjadi data nutrisi terstruktur.\n\nAturan:\n- Estimasi kalori dan makro per porsi yang disebutkan (default 1 porsi = 100 g makanan matang kecuali dinyatakan lain).\n- Nasi: 1 porsi = 200 g, kecuali \"1 mangkuk kecil\" = 150 g.\n- Telur: 1 butir = 60 g.\n- volume_eating = true hanya jika makanan rendah kalori (<150 kkal/100 g) DAN tinggi serat/air (sayur, buah, jamur).\n- Output HANYA JSON valid, tanpa penjelasan apapun."
    },
    {
      "role": "user",
      "content": "{\"text\":\"nasi putih 1 mangkuk sama ayam geprek\",\"instruction\":\"Isi JSON sesuai schema. Untuk makanan yang sudah ada di local_matches, pakai angka itu dan set source='local'. Estimasi sisanya dan set source='atria'.\",\"schema\":{\"foods\":[{\"name\":\"nama makanan\",\"kcal\":\"total kalori untuk porsi ini\",\"protein_g\":\"gram protein\",\"carb_g\":\"gram karbohidrat\",\"fat_g\":\"gram lemak\",\"portion_g\":\"gram porsi ini\",\"servings\":\"faktor porsi, default 1.0\",\"volume_eating\":\"boolean\"}],\"confidence\":\"number 0-1\",\"notes\":\"catatan singkat atau null\"},\"local_matches\":null}"
    }
  ]
}
```

### Response dari Atria (real, saat diuji)

```json
{
  "choices": [
    {
      "finish_reason": "stop",
      "message": {
        "role": "assistant",
        "content": "{\n  \"foods\": [\n    {\n      \"name\": \"Nasi putih\",\n      \"kcal\": 260,\n      \"protein_g\": 5.4,\n      \"carb_g\": 56.0,\n      \"fat_g\": 0.6,\n      \"portion_g\": 200,\n      \"servings\": 1.0,\n      \"volume_eating\": false\n    },\n    {\n      \"name\": \"Ayam geprek\",\n      \"kcal\": 280,\n      \"protein_g\": 24.0,\n      \"carb_g\": 12.0,\n      \"fat_g\": 17.0,\n      \"portion_g\": 100,\n      \"servings\": 1.0,\n      \"volume_eating\": false\n    }\n  ],\n  \"confidence\": 0.7,\n  \"notes\": \"Nasi putih 1 mangkuk dihitung 200 g (1 porsi standar). Ayam geprek estimasi 100 g per potong, nilai sudah termasuk sambal/tepung.\"}"
      }
    }
  ],
  "model": "Atria-Dawn-Preview"
}
```

### Response API ke frontend

```json
{
  "foods": [
    {
      "name": "Nasi putih",
      "kcal": 260,
      "protein_g": 5.4,
      "carb_g": 56.0,
      "fat_g": 0.6,
      "portion_g": 200,
      "servings": 1.0,
      "volume_eating": false,
      "source": "atria"
    },
    {
      "name": "Ayam geprek",
      "kcal": 280,
      "protein_g": 24.0,
      "carb_g": 12.0,
      "fat_g": 17.0,
      "portion_g": 100,
      "servings": 1.0,
      "volume_eating": false,
      "source": "atria"
    }
  ],
  "confidence": 0.7,
  "notes": "Nasi putih 1 mangkuk dihitung 200 g (1 porsi standar). Ayam geprek estimasi 100 g per potong, nilai sudah termasuk sambal/tepung.",
  "source": "atria"
}
```

---

## 2. Insight laporan mingguan (fitur #6)

### Request

```json
POST /api/ai/weekly-insights
{
  "week": {
    "start_date": "2026-10-05",
    "end_date": "2026-10-11",
    "target_kcal": 2122,
    "avg_kcal": 544,
    "avg_protein_g": 52.1,
    "protein_target_g": 135,
    "adherence": { "rate": 0.0, "days_logged": 6, "days_on_target": 0 },
    "plateau": true,
    "weight_trend": { "slope_per_day": -0.01, "change_kg": -0.7, "avg": 74.77 }
  }
}
```

Backend men-trim payload ke field yang dipakai (`_slim_week`) supaya
latensi reasoning model tetap masuk akal, lalu mengirim:

```json
{
  "model": "Atria-Dawn-Preview",
  "temperature": 0.4,
  "max_tokens": 1200,
  "messages": [
    {
      "role": "system",
      "content": "Kamu adalah coach nutrisi untuk Nurtra, aplikasi defisit kalori.\nInput: JSON ringkasan mingguan (text-only). Output: HANYA JSON valid, tanpa penjelasan.\nTugas: (1) analisis tren asupan vs target, (2) deteksi plateau bila berat badan stagnan >= 3 minggu, (3) rekomendasi konkret untuk minggu depan.\nBahasa Indonesia. Ringkas dan to the point."
    },
    {
      "role": "user",
      "content": "{\"schema\":{\"summary\":\"1-2 kalimat ringkasan minggu\",\"mood\":\"salah satu: on_track | plateau | over_target | under_eating | insufficient_data\",\"insights\":[{\"type\":\"protein | calories | plateau | fasting | exercise | hydration\",\"title\":\"string\",\"detail\":\"string\",\"severity\":\"info | warning | alert\"}],\"recommendations\":[{\"category\":\"nutrition | training | behavior\",\"action\":\"tindakan konkret untuk minggu depan\",\"rationale\":\"kenapa ini relevan dengan datanya\"}],\"next_week_target_kcal\":\"number atau null\",\"next_week_protein_g\":\"number atau null\",\"confidence\":\"number 0-1\"},\"week\":{\"start_date\":\"2026-10-05\",\"end_date\":\"2026-10-11\",\"target_kcal\":2122,\"avg_kcal\":544,\"avg_protein_g\":52.1,\"protein_target_g\":135,\"adherence\":{\"rate\":0.0,\"days_logged\":6,\"days_on_target\":0},\"plateau\":true,\"weight_trend\":{\"slope_per_day\":-0.01,\"change_kg\":-0.7,\"avg\":74.77}}}"
    }
  ]
}
```

### Response dari Atria (real)

```json
{
  "summary": "Asupan kalori sangat jauh di bawah target (rata-rata 544 dari 2122 kcal), protein hanya 39% dari target. Berat badan turun 0,7 kg namun plateau terdeteksi.",
  "mood": "under_eating",
  "insights": [
    {
      "type": "calories",
      "title": "Defisit kalori ekstrem",
      "detail": "Rata-rata 544 kcal/hari, hanya 26% dari target 2122. Defisit terlalu besar berisiko kehilangan massa otot dan rebound.",
      "severity": "alert"
    },
    {
      "type": "protein",
      "title": "Protein sangat kurang",
      "detail": "Asupan protein 52,1g dari target 135g. Protein rendah mempercepat katabolisme otot.",
      "severity": "warning"
    },
    {
      "type": "plateau",
      "title": "Plateau terdeteksi",
      "detail": "Bertahan pada berat yang sama selama 3+ minggu meski kalori sangat rendah, kemungkinan adaptasi metabolik.",
      "severity": "warning"
    }
  ],
  "recommendations": [
    {
      "category": "nutrition",
      "action": "Naikkan asupan mendekati target, prioritas protein 135g/hari dari dada ayam, tempe, telur.",
      "rationale": "Defisit ekstrem saat ini justru kontra-produktif untuk fat loss jangka panjang."
    }
  ],
  "next_week_target_kcal": 2122,
  "confidence": 0.85,
  "source": "atria"
}
```

---

## 3. Rekomendasi resep tinggi protein (fitur #2/#4)

### Request

```json
POST /api/ai/recipes
{
  "pantry": ["dada ayam", "nasi merah", "sawi", "telur"],
  "target_kcal": 500,
  "max_results": 3
}
```

### Response

```json
{
  "recipes": [
    {
      "name": "Chicken Rice Bowl Nurtra",
      "kcal": 520,
      "protein_g": 48.0,
      "carb_g": 55.0,
      "fat_g": 12.0,
      "ingredients": ["Dada Ayam Tanpa Kulit", "Nasi Merah", "Sawi Hijau"],
      "steps": [
        "Marinasi ayam dengan garam dan lada.",
        "Grill 6 menit per sisi.",
        "Tumis sawi sebentar.",
        "Sajikan dengan nasi merah."
      ],
      "prep_min": 20,
      "volume_eating": true,
      "tags": ["tinggi protein", "cepat"]
    }
  ],
  "source": "atria"
}
```

---

## Catatan kepatuhan text-only

Atria Dawn hanya memproses teks. Aturan yang diterapkan di `atria_client.py`:

- **Tidak ada input biner.** Backend tidak pernah mengirim `image_url` atau
  data base64. Hanya `text` content.
- **JSON sebagai string.** Data mentah (mingguan, makanan, pantry) diserialisasi
  ke JSON string lalu dibungkus sebagai user message.
- **Output dijaga tetap JSON.** `extract_json()` menangani model yang membungkus
  jawaban dalam ``` ```json fences atau menambahkan prose.
- **Fallback lokal.** Bila API gagal / timeout / belum ada key, ketiga fitur
  memakai `_local_*` yang deterministik — UI tidak pernah crash.
- **Latensi.** `Atria-Dawn-Preview` adalah reasoning model; `weekly-insights`
  butuh sekitar 45–130 detik. Timeout diset 240s, dan tombol UI menampilkan
  indikator "±1 menit".

---

## 4. Foto → nutrisi (fitur #7, provider terpisah)

Fitur ini **bukan** Atria Dawn — Atria text-only, jadi foto memakai Gemini
vision lewat endpoint OpenAI-compatible.

Endpoint: `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`
Model: `gemini-3.5-flash-lite`

```json
POST /api/ai/photo-foods
Content-Type: multipart/form-data

file: <image/jpeg atau image/png>
```

### Request ke Gemini

```json
{
  "model": "gemini-3.5-flash-lite",
  "temperature": 0.2,
  "max_tokens": 900,
  "messages": [{
    "role": "user",
    "content": [
      { "type": "text", "text": "<prompt identifikasi + schema>" },
      { "type": "image_url", "image_url": { "url": "data:image/jpeg;base64,..." } }
    ]
  }]
}
```

Gambar di-downsample ke 768px long edge (Pillow) sebelum diunggah karena
budget token Gemini ketat.

### Logika dua-sumber

1. Gemini mengembalikan `name` + `est_grams` per item.
2. Untuk setiap item, backend cari di database Indonesia (`search_foods`).
   - **Cocok** → angka nutrisi dari DB, diskalakan per gram. Konsisten
     dengan log teks user.
   - **Tidak cocok** → pakai estimasi Gemini, frontend menandai
     "estimasi AI" supaya user bisa edit.
3. Bila key Gemini kosong / quota habis / timeout → turun ke
   `candidates` dari DB + hint filename; user pilih manual.

### Batasan

- Gemini 3.x kadang membungkus JSON dalam ```json fences meski diminta
  tidak; `extract_json()` sudah menanganinya.
- Model reasoning: panggilan tanpa `max_tokens` bisa menghabiskan kuota
  per menit untuk "berpikir" tentang foto. Selalu set `max_tokens`.
- Free tier: ~20 request/hari per model (3.5-flash). Flash-lite punya
  kuota terpisah yang lebih longgar.
