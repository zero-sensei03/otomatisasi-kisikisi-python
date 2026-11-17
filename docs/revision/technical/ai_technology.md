# Teknologi AI

- Provider: `gemini` melalui `GeminiProvider`.
- Transport: HTTPX REST, endpoint `https://generativelanguage.googleapis.com/v1beta/interactions`, API path version `v1beta`; dependency bukan Google SDK.
- Default `AI_MODEL=gemini-3.1-flash-lite`; variabel `AI_MODEL` dapat mengganti nama model. Validitas nama dan availability perlu dikonfirmasi di akun Google AI Studio.
- API key berasal dari `GEMINI_API_KEY`, dibaca settings dari environment/`.env`. Key tidak ditulis di request log atau disimpan di DB.
- Timeout default `AI_TIMEOUT_SECONDS=90`. Request body memakai `model`, `input`, `response_format={type:text,mime_type:application/json}`, `store=false`. Source log menyatakan tidak mengirim generation config, system instruction terpisah, tools, safety settings, atau JSON schema native; prompt semua digabung di input dan divalidasi kemudian dengan Pydantic.
- Retry: HTTP 429/5xx ditandai retryable pada exception. GenerationService mencoba perbaikan output invalid secara terbatas; jumlah dan total percobaan mengikuti implementasi source. Tidak ada benchmark provider live pada paket ini.
- Token limit tidak dikonfigurasi secara eksplisit di request source. `max_material_characters` membatasi material, tetapi batas context/model aktual bergantung model/akun dan belum dikonfirmasi melalui metadata API.
- Error HTTP, timeout, malformed envelope/JSON dan schema dicatat dengan correlation id; pesan user disanitasi. Usage dicatat jika respons menyediakan `usage`.

Runtime versi FastAPI/SQLAlchemy/HTTPX/Python harus dibaca dari `reports/summary/environment.json` setelah runner. Ini membuat klaim versi dapat direproduksi dari mesin yang menjalankan paket.
