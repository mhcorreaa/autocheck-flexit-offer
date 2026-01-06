import time
import re
import os
import hashlib
import requests
from PIL import ImageGrab
import pytesseract
import cv2
import numpy as np
import pyautogui

# =========================
# CONFIGURACIÓN
# =========================

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

BBOX = (844, 241, 1198, 931)

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1457885394854088872/zcAjROxUg39I1lHap-9bjWkO4Cj0bdTnsR05UI8bLILefKAxeDzF99rcBHqdeBNzkt7n"

TARGETS = [
    "costanera center",
    "costanera",
    "mango",
    "mange",
    "tobalaba",
    "walker",
    "florida",
]

# Fin de lista (abajo)
END_MARKERS = [
    "más ofertas",
    "mas ofertas",
    "estan por venir",
    "están por venir",
    "por venir",
]

# Tope de lista (arriba)
TOP_MARKERS = [
    "metropolitana",
    "metropoli tana",   # por si OCR separa
    "metropo",          # fallback
]

INTERVAL_SECONDS = 1.2

# Swipe
DRAG_DURATION = 0.45
DRAG_PAUSE_DOWN = 0.85
DRAG_PAUSE_UP = 0.65

# Subida hasta el tope: límites de seguridad
MAX_UP_SWIPES_TO_TOP = 25      # por si el OCR falla, no se queda subiendo infinito
TOP_DETECT_STABLE_READS = 2    # pedir 2 lecturas seguidas para confirmar el tope

# Anti-spam
SEEN_FILE = "seen_hashes.txt"
MIN_SECONDS_BETWEEN_ALERTS = 10 * 60

pyautogui.FAILSAFE = True

# =========================
# DISCORD
# =========================
def send_discord(content: str) -> None:
    r = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=12)
    r.raise_for_status()

# =========================
# PERSISTENCIA + DEDUPE
# =========================
def load_seen() -> set[str]:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen(h: str) -> None:
    with open(SEEN_FILE, "a", encoding="utf-8") as f:
        f.write(h + "\n")

def normalize_for_hash(lines: list[str]) -> str:
    text = "\n".join(lines).lower()
    text = text.replace("falabelia", "falabella").replace("falabelta", "falabella")
    text = re.sub(r"\b\d{2}/\d{2}/\d{2,4}\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def block_hash(lines: list[str]) -> str:
    norm = normalize_for_hash(lines)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()

# =========================
# OCR
# =========================
def preprocess(pil_img):
    img = np.array(pil_img)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th

def ocr_text() -> str:
    shot = ImageGrab.grab(bbox=BBOX)
    th = preprocess(shot)
    config = "--oem 3 --psm 11"
    txt = pytesseract.image_to_string(th, lang="eng", config=config)
    txt = txt.replace("©", "").replace("€", "").replace("£", "")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{2,}", "\n", txt)
    return txt.strip()

def contains_any_marker(text: str, markers: list[str]) -> bool:
    t = text.lower()
    return any(m in t for m in markers)

def reached_end(text: str) -> bool:
    return contains_any_marker(text, END_MARKERS)

def reached_top(text: str) -> bool:
    return contains_any_marker(text, TOP_MARKERS)

def extract_matching_lines(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    low_targets = [t.lower() for t in TARGETS]
    return [ln for ln in lines if any(t in ln.lower() for t in low_targets)]

# =========================
# SWIPE SCROLL
# =========================
def scroll_down_swipe():
    # bajar lista = arrastrar hacia arriba
    x1, y1, x2, y2 = BBOX
    cx = (x1 + x2) // 2
    start_y = y1 + int((y2 - y1) * 0.85)
    end_y   = y1 + int((y2 - y1) * 0.15)
    pyautogui.moveTo(cx, start_y)
    pyautogui.dragTo(cx, end_y, duration=DRAG_DURATION, button="left")
    time.sleep(DRAG_PAUSE_DOWN)

def scroll_up_swipe():
    # subir lista = arrastrar hacia abajo
    x1, y1, x2, y2 = BBOX
    cx = (x1 + x2) // 2
    start_y = y1 + int((y2 - y1) * 0.15)
    end_y   = y1 + int((y2 - y1) * 0.85)
    pyautogui.moveTo(cx, start_y)
    pyautogui.dragTo(cx, end_y, duration=DRAG_DURATION, button="left")
    time.sleep(DRAG_PAUSE_UP)

def go_to_top_until_marker():
    """
    Sube haciendo swipes hasta que el OCR detecte TOP_MARKERS ("metropolitana").
    Usa confirmación por lecturas seguidas para evitar falsos positivos.
    """
    stable = 0
    for i in range(MAX_UP_SWIPES_TO_TOP):
        text = ocr_text()
        if reached_top(text):
            stable += 1
            if stable >= TOP_DETECT_STABLE_READS:
                print(f"🔼 Tope detectado ('metropolitana') en {i+1} swipes.")
                return True
        else:
            stable = 0

        scroll_up_swipe()

    print("⚠️ No pude confirmar el tope por OCR (metropolitana). Se alcanzó el máximo de swipes.")
    return False

# =========================
# MAIN
# =========================
def main():
    seen = load_seen()
    last_alert_time = 0.0

    print("Flexit -> Discord iniciado. Ctrl+C para salir.")
    print("FAILSAFE: mueve el mouse a la esquina sup-izq para cortar.")
    print(f"Vistos cargados: {len(seen)} (desde {SEEN_FILE})")
   
    while True:
        try:
            text = ocr_text()

            # Detecta targets
            matches = extract_matching_lines(text)
            if matches:
                h = block_hash(matches)
                now = time.time()

                if h not in seen and (now - last_alert_time) >= MIN_SECONDS_BETWEEN_ALERTS:
                    msg = "✅ Flexit: Oferta encontrada\n\n" + "\n".join(matches[:12])
                    send_discord(msg)
                    print("✅ Alerta enviada a Discord:\n", msg)

                    seen.add(h)
                    save_seen(h)
                    last_alert_time = now
                else:
                    if h in seen:
                        print("🔁 Match repetido (ya visto).")
                    else:
                        remaining = int(MIN_SECONDS_BETWEEN_ALERTS - (now - last_alert_time))
                        print(f"⏳ Rate-limit activo: faltan ~{remaining}s.")

            # Scroll (abajo hasta fin, luego subir hasta 'metropolitana')
            if reached_end(text):
                print("🛑 Fin de lista detectado")
                go_to_top_until_marker()
                time.sleep(2.0)
            else:
                scroll_down_swipe()

        except Exception as e:
            print("❌ Error:", e)

        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
