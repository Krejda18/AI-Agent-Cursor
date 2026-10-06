---
name: prepis-tematicke-shrnuti-audia
description: >-
  Z uživatelem dodané nahrávky udělá přepis v původním jazyce a české
  tematické shrnutí podle informací, které chce získat. Použij, když uživatel
  přiloží audio a napíše, co z něj potřebuje, nebo požádá o přepis či shrnutí
  nahrávky. Nahrávku nevyhledávej ani nestahuj.
---

# Přepis a tematické shrnutí audia

## Vstup

Uživatel dodá obojí:

1. audiosoubor,
2. co se z nahrávky má získat (otázka nebo seznam témat).

Soubor hledej v pracovním prostoru a v přílohách zprávy. Když už tam je, nevyžaduj nové nahrání a nic nestahuj. Nahrávku nevyhledávej na internetu, v archivech vysílatelů ani v podcastových katalozích.

Když soubor chybí, přepis nespouštěj. Napiš, že je potřeba přiložit nahrávku a zopakovat, jaké informace se mají získat. Netvrď, že nahrávka byla zpracovaná.

## Nástroj

Přepisuje lokální skript [scripts/transcribe.py](scripts/transcribe.py) modelem faster-whisper. Řeč zůstává na tomto stroji. Při prvním spuštění se stáhnou jen váhy modelu z Hugging Face (`Systran/faster-whisper-<model>`), ne nahrávka uživatele.

Prostředí, pokud ještě není:

```bash
python3 -m venv .venv
.venv/bin/pip install -r .cursor/skills/prepis-tematicke-shrnuti-audia/requirements.txt
```

Spuštění:

```bash
.venv/bin/python .cursor/skills/prepis-tematicke-shrnuti-audia/scripts/transcribe.py \
  CESTA_K_AUDIU \
  --output-dir output/transcripts
```

Výchozí model je `medium` na CPU, kvantizace `int8`. Nahrávku delší než 10 minut skript sám rozdělí na díly s překryvem 3 sekund, při spojení zahodí duplicity a časy přepočítá vůči začátku původního souboru. Výstupem je JSON a text s časovými značkami. Úplný přepis uživateli dej jen když o něj požádá; do shrnutí patří jen relevantní citace s časy.

Před shrnutím přečti v JSON pole `media` (formát, délka, počet dílů) a `language`. Přepis je v původním jazyce nahrávky, bez překladu. Shrnutí piš česky.

### Když lokální model nespustíš

Externí API je až záloha, a jen když lokální běh selže a v prostředí je `OPENAI_API_KEY`. Klíč čti pouze z prostředí. Nezapisuj ho do skillu, skriptu, commitu ani výstupních souborů.

Než nahrávku odešleš, napiš uživateli v odpovědi, kam půjde. U tohoto skriptu je to `https://api.openai.com/v1/audio/transcriptions` (OpenAI). Bez tohoto upozornění příkaz nespouštěj. Skript externí odeslání sám odmítne, dokud nedostane `--confirm-external-upload`, a cíl stejně vypíše na chybový výstup.

```bash
.venv/bin/python .cursor/skills/prepis-tematicke-shrnuti-audia/scripts/transcribe.py \
  CESTA_K_AUDIU \
  --output-dir output/transcripts \
  --provider openai \
  --confirm-external-upload
```

## Postup

1. Načti dodaný audiosoubor. Když v pracovním prostoru už je, nevyžaduj nové nahrání.
2. Zkontroluj formát, délku a limity. Lokální model nemá pevný strop délky; dlouhé soubory jdou po dílech. OpenAI přijímá nejvýše 25 MB na jeden požadavek, skript je v té větvi také dělí.
3. Podle potřeby převeď audio do WAV 16 kHz mono. Dlouhé nahrávky nech rozdělit s krátkým překryvem.
4. Přepiš celou nahrávku v původním jazyce a zachovej časové značky. Duplicity z překryvu nech skript odstranit a časy nech přepočítat vůči původní nahrávce.
5. Nesrozumitelná místa nech označená jako `[nesrozumitelné]`. Nedoplňuj odhadem jména, čísla, právní podmínky ani jiná chybějící fakta. Nejistý segment zůstává s původním zněním a značkou `[nejisté]`.
6. Vyhledej pasáže relevantní k tomu, co uživatel chce získat. Zohledni i související vysvětlení a výjimky z jiných částí nahrávky.
7. Vytvoř stručné české shrnutí. Ke klíčovým bodům přidej časové odkazy na nahrávku ve tvaru `mm:ss` nebo `h:mm:ss`.
8. Jasně rozlišuj tvrzení účastníků, jejich názory a nejistoty. Pokud audio na otázku neodpovídá, výslovně to uveď. U tématu, které v nahrávce nezaznělo, napiš, že v ní není, a nic za něj nedoplňuj.
9. Právní či jiné časově proměnlivé informace nepředkládej automaticky jako aktuálně platné. Jsou to údaje z nahrávky k datu jejího pořízení. Případné ověření z oficiálních zdrojů uveď odděleně od shrnutí audia, včetně data ověření a odkazů.
10. Pokud přepis selže, popiš konkrétní problém (chybějící soubor, nečitelný formát, pád modelu, prázdný výsledek, odmítnuté API) a potřebný další krok. Nikdy netvrď, že jsi nahrávku zpracoval, pokud se to nepodařilo.

## Výstup pro uživatele

- Krátká přímá odpověď na to, co chtěl získat.
- Přehled hlavních bodů s časovými značkami.
- Podmínky, výjimky a nejasnosti zmíněné v audiu.
- Úplný přepis jen na vyžádání.

## Slack

Když uživatel chce výstup ve Slacku, pošli tam stejné české shrnutí. Úplný přepis do Slacku nedávej, pokud o něj výslovně nepožádá.

- Kanál ber jen z jeho zadání. Když kanál neuvede, ulož koncept do jeho vlastní přímé zprávy nástrojem pro koncept zprávy, ať text před odesláním vidí.
- Do pojmenovaného kanálu zprávu odešli rovnou jen tehdy, když o odeslání výslovně požádá. Jinak nech koncept.
- Text piš běžným markdownem. Na začátek dej přímou odpověď, pak body s časy a nakonec podmínky, výjimky a nejasnosti.
- Do zprávy nepiš klíč k přepisu, cestu k nahrávce ani nic, co v audiu nezaznělo.

Do git commitu nepatří nahrávka, váhy modelu ani soubory z `output/`.
