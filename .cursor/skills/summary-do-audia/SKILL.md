---
name: summary-do-audia
description: >-
  Converts a written summary into a spoken mp3. Use when the user asks to turn
  a summary, shrnutí, přepis, or other text into audio, a voice file, or mp3.
---

# Shrnutí do audia

Z textu udělej namluvené mp3. Nepřidávej obsah, který v textu není.

## Postup

1. Vezmi text, který uživatel určil. Když žádný nepošle, vezmi poslední shrnutí z této konverzace, včetně shrnutí ze skillu `prepis-audia`.
2. Ulož ho do dočasného `.txt` v UTF-8. Do gitu ho nedávej.
3. Prostředí, pokud ještě není:

```bash
python3 -m venv .venv
.venv/bin/pip install -r .cursor/skills/summary-do-audia/requirements.txt
```

4. Spusť:

```bash
.venv/bin/python .cursor/skills/summary-do-audia/scripts/summary_to_audio.py \
  vstup.txt \
  -o output/audio/summary.mp3
```

Mužský hlas: přidej `--male`. Jiný hlas: `--voice cs-CZ-AntoninNeural` nebo `--voice sk-SK-ViktoriaNeural`.

5. Výstup skriptu je `cesta<TAB>hlas<TAB>délka_v_sekundách`. Tu cestu uživateli řekni a napiš, jak je nahrávka dlouhá. Mp3 nikam nenahrávej a necommituj, dokud o to nepožádá. `output/` a `*.mp3` jsou v `.gitignore`.

## Hlas

Výchozí je čeština, ženský hlas `cs-CZ-VlastaNeural`. Jazyk textu neměň. Markdown (nadpisy, tučné písmo, odrážky) skript před namluvením odstraní.
