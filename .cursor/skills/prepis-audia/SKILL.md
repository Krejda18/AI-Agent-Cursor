---
name: prepis-audia
description: >-
  Z vložené nahrávky nebo z vloženého odkazu na podcast udělá přepis v původním
  jazyce a české shrnutí celého podcastu. Postup spusť automaticky, jakmile je
  ve zprávě audio nebo odkaz na epizodu; na další zadání nečekej. U fotbalu,
  lig a hráčů uvede konkrétní hráče a důvod, proč se o nich mluví. Pořad podle
  názvu nevyhledávej. Stáhni jen audio z odkazu, který uživatel vložil.
---

# Přepis audia

## Automatické spuštění

Jakmile je ve zprávě audiosoubor nebo odkaz na podcast, spusť celý postup hned. Neptej se, co z nahrávky získat, a nečekej na další pokyn. Text vedle souboru nebo odkazu je jen doplněk. Shrnutí pořád pokryje celou epizodu.

Spouští to kterákoliv z těchto věcí:

- přiložený audiosoubor
- odkaz na audiosoubor (mp3, m4a, m4b, aac, ogg, wav, opus, flac)
- odkaz na stránku jedné epizody
- odkaz na RSS nebo Atom položku
- odkaz na feed pořadu; z něj vezmi jen nejnovější epizodu a ve shrnutí uveď její název

Pořad nevyhledávej podle názvu, v katalogu, v archivu vysílatele ani na webu. Stahuj jen z odkazu, který uživatel vložil.

Když chybí soubor i odkaz, přepis nespouštěj. Napiš, že je potřeba vložit nahrávku nebo odkaz na epizodu. Netvrď, že nahrávka byla zpracovaná.

## Vstup

Soubor hledej v pracovním prostoru a v přílohách zprávy. Když už tam je, nevyžaduj nové nahrání.

Odkaz předej skriptu [scripts/fetch_audio.py](scripts/fetch_audio.py). Ten uloží jednu epizodu do `output/audio` a na standardní výstup vypíše JSON s cestou, názvem dílu a polem `selection`.

```bash
.venv/bin/python .cursor/skills/prepis-audia/scripts/fetch_audio.py \
  VLOZENY_ODKAZ \
  --output-dir output/audio
```

- `direct` nebo `page` znamená soubor z vloženého odkazu nebo ze stránky té epizody.
- `feed_item` znamená díl, na který odkaz mířil.
- `feed_latest` znamená, že odkaz vedl na celý feed. Ve shrnutí napiš název z `episode_title` a že jde o nejnovější díl toho feedu.
- Když stránka nabízí víc zvuků a není jasné, který je epizoda, skript se zastaví. Předej uživateli jeho hlášku a přepis nespouštěj.
- Když odkaz zvuk nevydá, typicky přehrávač bez souboru, přihlášení nebo zamčená epizoda, skript se zastaví. Přepis nespouštěj a netvrď, že nahrávka byla zpracovaná.
- Stažený soubor necommituj. Patří do `output/`, který je v `.gitignore`.

## Nástroj

Přepisuje lokální skript [scripts/transcribe.py](scripts/transcribe.py) modelem faster-whisper. Řeč zůstává na tomto stroji. Při prvním spuštění se stáhnou jen váhy modelu z Hugging Face (`Systran/faster-whisper-<model>`), ne nahrávka uživatele.

Prostředí, pokud ještě není:

```bash
python3 -m venv .venv
.venv/bin/pip install -r .cursor/skills/prepis-audia/requirements.txt
```

Spuštění:

```bash
.venv/bin/python .cursor/skills/prepis-audia/scripts/transcribe.py \
  CESTA_K_AUDIU \
  --output-dir output/transcripts
```

Výchozí model je `medium` na CPU, kvantizace `int8`. Nahrávku delší než 10 minut skript sám rozdělí na díly s překryvem 3 sekund, při spojení zahodí duplicity a časy přepočítá vůči začátku původního souboru. Výstupem je JSON a text s časovými značkami. Úplný přepis uživateli dej jen když o něj požádá; do shrnutí patří jen relevantní citace s časy.

Před shrnutím přečti v JSON pole `media` (formát, délka, počet dílů) a `language`. Přepis je v původním jazyce nahrávky, bez překladu. Shrnutí piš česky.

### Když lokální model nespustíš

Externí API je až záloha, a jen když lokální běh selže a v prostředí je `OPENAI_API_KEY`. Klíč čti pouze z prostředí. Nezapisuj ho do skillu, skriptu, commitu ani výstupních souborů.

Než nahrávku odešleš, napiš uživateli v odpovědi, kam půjde. U tohoto skriptu je to `https://api.openai.com/v1/audio/transcriptions` (OpenAI). Bez tohoto upozornění příkaz nespouštěj. Skript externí odeslání sám odmítne, dokud nedostane `--confirm-external-upload`, a cíl stejně vypíše na chybový výstup.

```bash
.venv/bin/python .cursor/skills/prepis-audia/scripts/transcribe.py \
  CESTA_K_AUDIU \
  --output-dir output/transcripts \
  --provider openai \
  --confirm-external-upload
```

## Postup

1. Vezmi přiložené audio, nebo z vloženého odkazu stáhni jednu epizodu. Na další zadání nečekej. Když není ani soubor, ani odkaz, zastav se.
2. Zkontroluj formát, délku a limity. Lokální model nemá pevný strop délky; dlouhé soubory jdou po dílech. OpenAI přijímá nejvýše 25 MB na jeden požadavek, skript je v té větvi také dělí.
3. Podle potřeby převeď audio do WAV 16 kHz mono. Dlouhé nahrávky nech rozdělit s krátkým překryvem.
4. Přepiš celou nahrávku v původním jazyce a zachovej časové značky. Duplicity z překryvu nech skript odstranit a časy nech přepočítat vůči původní nahrávce.
5. Nesrozumitelná místa nech označená jako `[nesrozumitelné]`. Nedoplňuj odhadem jména, čísla, právní podmínky ani jiná chybějící fakta. Nejistý segment zůstává s původním zněním a značkou `[nejisté]`.
6. Shrň celou nahrávku. Nevynech pozdější část jen proto, že úvod už téma naznačil. Zohledni vysvětlení, výjimky a obraty z jiných míst epizody.
7. Vytvoř české shrnutí celého podcastu. Ke klíčovým bodům přidej časové odkazy na nahrávku ve tvaru `mm:ss` nebo `h:mm:ss`.
8. Jasně rozlišuj tvrzení účastníků, jejich názory a nejistoty. Jméno, klub, číslo nebo důvod uváděj jen tehdy, když v nahrávce zazněly. Když je pasáž nesrozumitelná, napiš to a nic za ni nedoplňuj.
9. Právní či jiné časově proměnlivé informace nepředkládej automaticky jako aktuálně platné. Jsou to údaje z nahrávky k datu jejího pořízení. Případné ověření z oficiálních zdrojů uveď odděleně od shrnutí audia, včetně data ověření a odkazů.
10. Pokud stažení nebo přepis selže, popiš konkrétní problém (chybějící soubor, odkaz beze zvuku, víc souborů na stránce, nečitelný formát, pád modelu, prázdný výsledek, odmítnuté API) a potřebný další krok. Nikdy netvrď, že jsi nahrávku zpracoval, pokud se to nepodařilo.

## Shrnutí celého podcastu

Shrnutí má pokrýt celou epizodu: o čem je, jak se debata posouvá a čím končí. Každý podstatný bod má čas.

Když je podcast o fotbale, ligách nebo hráčích, uveď konkrétní hráče, o kterých se mluví, a u každého důvod té debaty tak, jak ho říkají účastníci. Důvod může být forma, zranění, přestup, sestava, trest, výkon v zápase nebo spor v diskusi. Hráče, kteří v nahrávce nezazněli, nepřidávej. U nejistě rozpoznaného jména nech značku `[nejisté]` a nevymýšlej klub ani důvod.

## Výstup pro uživatele

- O čem celý podcast je.
- Průběh po tématech, s časovými značkami.
- U fotbalu seznam hráčů a důvod, proč se o nich mluví.
- Podmínky, výjimky a nejasnosti zmíněné v audiu.
- Úplný přepis jen na vyžádání.

## Slack

Veřejný kanál `#prepis-audia` (`C0C78B1UKBK`) je vyhrazený jen tomuto skillu. Když tě spustí zpráva z tohoto kanálu a je v ní audio nebo odkaz na podcast, spusť celý postup automaticky. Na další zadání nečekej. Ve zprávě stačí nahrávka nebo odkaz; uživatel nemusí psát, co z nich chce. Jiný úkol odmítni jednou větou a požádej o nahrávku nebo odkaz.

Odpověz ve vlákně té zprávy, která tě zavolala. České shrnutí pošli tam. Úplný přepis do Slacku nedávej, pokud o něj výslovně nepožádá.

- Mimo tento kanál ber cílový kanál jen ze zadání. Když kanál neuvede, ulož koncept do jeho vlastní přímé zprávy, ať text před odesláním vidí.
- Do jiného pojmenovaného kanálu zprávu odešli rovnou jen tehdy, když o odeslání výslovně požádá.
- Text piš běžným markdownem. Na začátek dej, o čem celý podcast je, pak průběh s časy. U fotbalu přidej hráče a důvod debaty. Nakonec podmínky, výjimky a nejasnosti.
- Do zprávy nepiš klíč k přepisu, cestu k nahrávce ani nic, co v audiu nezaznělo.
- Kód v repozitáři neměň a pull request nezakládej, pokud o to uživatel ve stejné zprávě výslovně nepožádá.

Do git commitu nepatří nahrávka, váhy modelu ani soubory z `output/`.
