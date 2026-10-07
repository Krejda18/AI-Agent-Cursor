---
name: prepis-audio
description: >-
  Z uživatelem dodaného audiosouboru nebo odkazu na jeden podcast udělá přepis
  v původním jazyce a české shrnutí celé epizody. Použij, když uživatel přiloží
  audio, vloží odkaz na díl, Overcast, RSS položku nebo feed, nebo požádá o
  přepis či shrnutí jedné nahrávky. Pořad podle názvu nevyhledávej. Týdenní
  průchod sledovaných pořadů patří skillu tydenni-fotbalove-podcasty.
---

# Přepis audia

## Kdy skill použít

Spusť ho, jakmile je ve zprávě jeden audiosoubor nebo jeden odkaz na podcast. Neptej se, co z nahrávky získat. Text vedle souboru je jen doplněk. Shrnutí pokryje celou epizodu.

Týdenní seznam sledovaných pořadů tímto skillem neprocházej. To dělá skill `tydenni-fotbalove-podcasty`.

## Složka

Kořen skillu je složka s tímto `SKILL.md`. Skripty, `requirements.txt` i `.venv` ber z toho kořene. Ve všech projektech leží v `~/.cursor/skills/prepis-audio`, v tomto repozitáři v `.cursor/skills/prepis-audio`.

```bash
SKILL_DIR="<kořen tohoto skillu>"
WORK_DIR="${TMPDIR:-/tmp}/prepis-audio"
```

Stažené audio a přepis nech v `$WORK_DIR`. Do git commitu nepatří.

## Automatické spuštění

Stačí jedna z těchto věcí:

- přiložený audiosoubor
- odkaz na audiosoubor (mp3, m4a, m4b, aac, ogg, wav, opus, flac)
- odkaz na stránku jedné epizody, včetně Overcast (`https://overcast.fm/+...`); ze stránky vezmi vložený zvuk a sleduj přesměrování až k souboru
- odkaz na RSS nebo Atom položku
- odkaz na feed pořadu; z něj vezmi jen nejnovější epizodu a uveď její název

Pořad nevyhledávej podle názvu, v katalogu ani v archivu vysílatele. Stahuj jen z odkazu, který uživatel vložil. Když soubor ani odkaz není, přepis nespouštěj a napiš, že je potřeba nahrávku nebo odkaz. Netvrď, že nahrávka byla zpracovaná.

## Stažení a přepis

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/fetch_audio.py" \
  VLOZENY_ODKAZ \
  --output-dir "$WORK_DIR/audio"
```

Když `.venv` chybí:

```bash
python3 -m venv "$SKILL_DIR/.venv"
"$SKILL_DIR/.venv/bin/pip" install -r "$SKILL_DIR/requirements.txt"
```

Přepis je lokální faster-whisper. Řeč zůstává na tomto stroji. Z Hugging Face se stáhnou jen váhy modelu.

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/transcribe.py" \
  CESTA_K_AUDIU \
  --output-dir "$WORK_DIR/transcripts"
```

Model je `medium`, CPU, `int8`. Nahrávku delší než 10 minut skript dělí s překryvem 3 sekund, duplicity zahodí a časy přepočítá vůči začátku souboru. Před shrnutím přečti v JSON pole `media` a `language`. Přepis je v původním jazyce. Shrnutí piš česky. Úplný přepis dej jen na vyžádání.

`direct` a `page` jsou soubor z odkazu nebo ze stránky epizody. `feed_item` je díl, na který odkaz mířil. `feed_latest` je nejnovější díl feedu; uveď název z `episode_title`. Když stránka má víc zvuků, nebo zvuk nevydá, předej hlášku skriptu a přepis nespouštěj.

### Záloha OpenAI

Až když lokální běh selže a v prostředí je `OPENAI_API_KEY`. Klíč nepiš do skillu, skriptu, commitu ani výstupu. Než nahrávku odešleš, napiš, že cíl je `https://api.openai.com/v1/audio/transcriptions`. Bez tohoto upozornění příkaz nespouštěj.

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/transcribe.py" \
  CESTA_K_AUDIU \
  --output-dir "$WORK_DIR/transcripts" \
  --provider openai \
  --confirm-external-upload
```

## Postup

1. Vezmi přiložené audio, nebo z vloženého odkazu stáhni jednu epizodu.
2. Zkontroluj formát a délku. Dlouhé soubory jdou po dílech.
3. Přepiš celou nahrávku v původním jazyce a zachovej časové značky.
4. Nesrozumitelná místa nech jako `[nesrozumitelné]`. Nedoplňuj jména, čísla ani jiná chybějící fakta. Nejistý segment nech se značkou `[nejisté]`.
5. Shrň celou epizodu. Nevynech pozdější část jen proto, že úvod téma naznačil.
6. Ke klíčovým bodům přidej čas `mm:ss` nebo `h:mm:ss`. Rozlišuj tvrzení, názory a nejistoty.
7. Jméno, klub, číslo nebo důvod uváděj jen tehdy, když v nahrávce zazněly.
8. Právní a jiné časově proměnlivé údaje ber jako obsah nahrávky k datu pořízení, ne jako ověřený platný stav.
9. Když stažení nebo přepis selže, popiš problém. Netvrď, že nahrávka byla zpracovaná.

Když je podcast o fotbale, ligách nebo hráčích, uveď konkrétní hráče a důvod, proč se o nich mluví: forma, zranění, přestup, sestava, trest, výkon nebo spor. Hráče, kteří nezazněli, nepřidávej.

## Výstup

- O čem celý podcast je.
- Průběh po tématech, s časy.
- U fotbalu seznam hráčů a důvod debaty.
- Podmínky, výjimky a nejasnosti.
- Úplný přepis jen na vyžádání.

## Slack

Kanál `#prepis-audia` (`C0C78B1UKBK`) je pro tento skill, když zpráva obsahuje audio nebo jeden odkaz. Odpověz ve vlákně česky. Úplný přepis do Slacku nedávej, pokud o něj nepožádá. Žádost o týdenní průchod sledovaných pořadů odmítni jednou větou a použij skill `tydenni-fotbalove-podcasty`.

Mimo tento kanál ber cílový kanál jen ze zadání. Když kanál neuvede, ulož koncept do vlastní přímé zprávy. Do pojmenovaného kanálu odešli zprávu jen na výslovnou žádost. Do zprávy nepiš klíč, cestu k nahrávce ani nic, co v audiu nezaznělo. Kód neměň a pull request nezakládej, pokud o to uživatel ve stejné zprávě nepožádá.
