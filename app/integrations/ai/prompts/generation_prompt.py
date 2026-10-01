import json

from app.integrations.ai.schemas import AIGenerationRequest

def build_generation_prompt(request: AIGenerationRequest, *, repair: bool = False, repair_context: dict | None = None) -> str:
    instruction = "Buat rangkuman dan soal berdasarkan materi."
    repair_section = ""
    if repair:
        instruction = "Perbaiki output AI sebelumnya menjadi JSON valid sesuai schema dan jumlah soal yang diminta."
        if repair_context:
            previous = repair_context.get("previous_response", "")
            feedback = repair_context.get("feedback", "Respons sebelumnya gagal validasi.")
            repair_section = f"\nOutput sebelumnya yang harus diperbaiki:\n{previous}\nMasalah validasi:\n{feedback}\n"
    return f"""{instruction}
PRIMARY MATERIAL adalah sumber utama; REFERENCE MATERIAL hanya sumber pendukung.
Pahami materi. Buat rangkuman, soal, jawaban, pembahasan, dan kisi-kisi. Sesuaikan dengan subject dan class. Semua soal harus relevan dan tidak bertentangan dengan materi.
Jumlah tipe soal harus tepat sesuai question_distribution. Nilai field type dan question_type WAJIB persis salah satu string uppercase ini: MULTIPLE_CHOICE, SHORT_ANSWER, ESSAY. Jangan gunakan lowercase atau terjemahan. Pilihan ganda wajib opsi A-D dan tepat satu is_correct=true. answer harus label yang benar dan pembahasan sesuai jawaban. Setiap soal punya satu blueprint. Gunakan cognitive_level C1-C6 dan difficulty EASY/MEDIUM/HARD. Isian dan essay tidak punya options; jawaban essay boleh contoh atau rubrik.
Kembalikan JSON ONLY. Tanpa markdown, code fence, ataupun penjelasan sebelum/sesudah JSON.
Schema key types: summary is string; questions is an array of objects with number integer, type string, question string, options array of four {{label,text,is_correct}} objects for multiple choice, answer string, explanation string; blueprint is an array with number, question_number, material_topic, learning_objective, indicator, question_type, cognitive_level, difficulty.
Input: {json.dumps(request.model_dump(), ensure_ascii=False)}{repair_section}"""
