import re
import zlib

MAX_DECOMPRESSED_BYTES = 24 * 1024 * 1024


def extract_pdf(data: bytes) -> str:
    chunks = []
    decompressed_total = 0
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", data, flags=re.S):
        candidates = [stream]
        try:
            decompressor = zlib.decompressobj()
            expanded = decompressor.decompress(stream, MAX_DECOMPRESSED_BYTES - decompressed_total + 1)
            if decompressor.unconsumed_tail or len(expanded) + decompressed_total > MAX_DECOMPRESSED_BYTES:
                raise ValueError("Konten PDF terlalu besar untuk diproses.")
            decompressed_total += len(expanded)
            candidates.insert(0, expanded)
        except zlib.error:
            pass
        for content in candidates:
            for value in re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", content):
                chunks.append(value.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\").decode("utf-8", "ignore"))
            for array in re.findall(rb"\[(.*?)\]\s*TJ", content, flags=re.S):
                chunks.extend(value.decode("utf-8", "ignore") for value in re.findall(rb"\((.*?)\)", array, flags=re.S))
    return "\n".join(chunks)
