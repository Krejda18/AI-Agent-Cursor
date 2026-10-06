---
name: prepis-audia
description: >-
  Z vložené nahrávky, odkazu na podcast nebo z týdenního seznamu sledovaných
  pořadů udělá přepis a česky vytáhne finance klubů, hráče ve formě i mimo ni,
  mladé hráče a nabídky na hráče. Ze všech podcastů jedné země udělá ještě
  celkový souhrn. Postup spusť automaticky, jakmile je ve
  zprávě audio, odkaz, nebo žádost o týdenní průchod. Pořad podle názvu
  nevyhledávej. Stáhni jen audio z odkazu, který uživatel vložil.
---

# Přepis audia

## Složka pro všechny projekty

Skill platí ve všech projektech, když leží v `~/.cursor/skills/prepis-audia`. Stejný obsah je v tomto repozitáři v `.cursor/skills/prepis-audia`, aby ho našel agent spuštěný z tohoto projektu.

Kořen skillu je složka, ve které je tento `SKILL.md`. Skripty, `requirements.txt` i `.venv` ber z toho kořene. Cesty `.cursor/skills/...` nepoužívej, v jiném projektu tam skill není.

Stažené audio a přepis ukládej do dočasné složky, ne do stromu cizího projektu:

```bash
SKILL_DIR="<kořen tohoto skillu>"
WORK_DIR="${TMPDIR:-/tmp}/prepis-audia"
```

## Automatické spuštění

Jakmile je ve zprávě audiosoubor nebo odkaz na podcast, spusť celý postup hned. Neptej se, co z nahrávky získat, a nečekej na další pokyn. Text vedle souboru nebo odkazu je jen doplněk. Výstup vytáhne informace o klubech, hráčích a nabídkách z celé epizody.

Když uživatel požádá o týdenní průchod, nebo je pondělní běh sledovaných pořadů, použij postup v části Týdenní průchod. Na další zadání nečekej.

Spouští to kterákoliv z těchto věcí:

- přiložený audiosoubor
- odkaz na audiosoubor (mp3, m4a, m4b, aac, ogg, wav, opus, flac)
- odkaz na stránku jedné epizody, včetně sdíleného přehrávače jako Overcast (`https://overcast.fm/+...`); ze stránky vezmi vložený zvuk a sleduj přesměrování až k souboru
- odkaz na RSS nebo Atom položku
- odkaz na feed pořadu; z něj vezmi jen nejnovější epizodu a ve shrnutí uveď její název

Pořad nevyhledávej podle názvu, v katalogu, v archivu vysílatele ani na webu. Stahuj jen z odkazu, který uživatel vložil.

Když chybí soubor i odkaz, přepis nespouštěj. Napiš, že je potřeba vložit nahrávku nebo odkaz na epizodu. Netvrď, že nahrávka byla zpracovaná.

## Vstup

Soubor hledej v pracovním prostoru a v přílohách zprávy. Když už tam je, nevyžaduj nové nahrání.

Odkaz předej skriptu [scripts/fetch_audio.py](scripts/fetch_audio.py). Ten uloží jednu epizodu do `$WORK_DIR/audio` a na standardní výstup vypíše JSON s cestou, názvem dílu a polem `selection`.

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/fetch_audio.py" \
  VLOZENY_ODKAZ \
  --output-dir "$WORK_DIR/audio"
```

- `direct` nebo `page` znamená soubor z vloženého odkazu nebo ze stránky té epizody.
- `feed_item` znamená díl, na který odkaz mířil.
- `feed_latest` znamená, že odkaz vedl na celý feed. Ve shrnutí napiš název z `episode_title` a že jde o nejnovější díl toho feedu.
- Když stránka nabízí víc zvuků a není jasné, který je epizoda, skript se zastaví. Předej uživateli jeho hlášku a přepis nespouštěj.
- Když odkaz zvuk nevydá, typicky přehrávač bez souboru, přihlášení nebo zamčená epizoda, skript se zastaví. Přepis nespouštěj a netvrď, že nahrávka byla zpracovaná.
- Stažený soubor necommituj. Nech ho v `$WORK_DIR`.

## Nástroj

Přepisuje lokální skript [scripts/transcribe.py](scripts/transcribe.py) modelem faster-whisper. Řeč zůstává na tomto stroji. Při prvním spuštění se stáhnou jen váhy modelu z Hugging Face (`Systran/faster-whisper-<model>`), ne nahrávka uživatele.

Prostředí, pokud ještě není:

```bash
python3 -m venv "$SKILL_DIR/.venv"
"$SKILL_DIR/.venv/bin/pip" install -r "$SKILL_DIR/requirements.txt"
```

Spuštění:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/transcribe.py" \
  CESTA_K_AUDIU \
  --output-dir "$WORK_DIR/transcripts"
```

Výchozí model je `medium` na CPU, kvantizace `int8`. Nahrávku delší než 10 minut skript sám rozdělí na díly s překryvem 3 sekund, při spojení zahodí duplicity a časy přepočítá vůči začátku původního souboru. Výstupem je JSON a text s časovými značkami. Úplný přepis uživateli dej jen když o něj požádá; do shrnutí patří jen relevantní citace s časy.

Před shrnutím přečti v JSON pole `media` (formát, délka, počet dílů) a `language`. Přepis je v původním jazyce nahrávky, bez překladu. Shrnutí piš česky.

### Když lokální model nespustíš

Externí API je až záloha, a jen když lokální běh selže a v prostředí je `OPENAI_API_KEY`. Klíč čti pouze z prostředí. Nezapisuj ho do skillu, skriptu, commitu ani výstupních souborů.

Než nahrávku odešleš, napiš uživateli v odpovědi, kam půjde. U tohoto skriptu je to `https://api.openai.com/v1/audio/transcriptions` (OpenAI). Bez tohoto upozornění příkaz nespouštěj. Skript externí odeslání sám odmítne, dokud nedostane `--confirm-external-upload`, a cíl stejně vypíše na chybový výstup.

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/transcribe.py" \
  CESTA_K_AUDIU \
  --output-dir "$WORK_DIR/transcripts" \
  --provider openai \
  --confirm-external-upload
```

## Postup

1. Vezmi přiložené audio, nebo z vloženého odkazu stáhni jednu epizodu. Když jde o týdenní průchod, vezmi odkazy ze `sledovane.txt`. Na další zadání nečekej. Když není soubor, odkaz ani týdenní seznam, zastav se.
2. Zkontroluj formát, délku a limity. Lokální model nemá pevný strop délky; dlouhé soubory jdou po dílech. OpenAI přijímá nejvýše 25 MB na jeden požadavek, skript je v té větvi také dělí.
3. Podle potřeby převeď audio do WAV 16 kHz mono. Dlouhé nahrávky nech rozdělit s krátkým překryvem.
4. Přepiš celou nahrávku v původním jazyce a zachovej časové značky. Duplicity z překryvu nech skript odstranit a časy nech přepočítat vůči původní nahrávce.
5. Nesrozumitelná místa nech označená jako `[nesrozumitelné]`. Nedoplňuj odhadem jména, čísla, právní podmínky ani jiná chybějící fakta. Nejistý segment zůstává s původním zněním a značkou `[nejisté]`.
6. Projdi celý přepis. Nevynech pozdější část jen proto, že úvod už téma naznačil. Zohledni vysvětlení, výjimky a obraty z jiných míst epizody.
7. Vytáhni česky šest skupin z části Co z přepisu vytáhnout. Ke každé položce přidej čas `mm:ss` nebo `h:mm:ss`.
8. Jasně rozlišuj tvrzení účastníků, jejich názory a nejistoty. Jméno, klub, číslo nebo důvod uváděj jen tehdy, když v nahrávce zazněly. Když je pasáž nesrozumitelná, napiš to a nic za ni nedoplňuj.
9. Právní či jiné časově proměnlivé informace nepředkládej automaticky jako aktuálně platné. Jsou to údaje z nahrávky k datu jejího pořízení. Případné ověření z oficiálních zdrojů uveď odděleně od shrnutí audia, včetně data ověření a odkazů.
10. Pokud stažení nebo přepis selže, popiš konkrétní problém (chybějící soubor, odkaz beze zvuku, víc souborů na stránce, nečitelný formát, pád modelu, prázdný výsledek, odmítnuté API) a potřebný další krok. Nikdy netvrď, že jsi nahrávku zpracoval, pokud se to nepodařilo.

## Týdenní průchod

Jednou týdně projdi sledované podcasty. Seznam odkazů je v [sledovane.txt](sledovane.txt) ve složce skillu. Jeden odkaz na řádek: RSS feed, stránka epizody, Overcast nebo přímý soubor. Řádky s `#` a prázdné řádky přeskoč. Pořad podle názvu nevyhledávej. Když v souboru není žádný odkaz, průchod zastav a napiš, že seznam je prázdný. Nic nestahuj a netvrď, že epizody byly zpracované.

Když uživatel pošle OPML, přepiš `sledovane.txt` adresami z `xmlUrl`. Název pořadu a skupinu nech na řádcích s `#`. Jiné pořady do seznamu nepřidávej.

Už přepsané díly jsou v [zpracovane.txt](zpracovane.txt), jeden `media_url` na řádek. Ty přeskoč.

Pro každý odkaz stáhni díly z posledních 7 dní:

```bash
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/fetch_audio.py" \
  ODKAZ_ZE_SEZNAMU \
  --output-dir "$WORK_DIR/audio" \
  --recent-days 7
```

Výstup je JSON pole. `feed_recent` jsou díly s datem v posledních 7 dnech. `feed_latest` znamená, že feed datum nemá, takže je stažený jen nejnovější díl; ve zprávě to napiš. Prázdné pole znamená, že tento týden nový díl nevyšel. Odkaz na jednu epizodu nebo přehrávač stáhne ten jeden díl.

Každý nový soubor přepiš celý. Až přepis existuje, dopiš jeho `media_url` do `zpracovane.txt`. Když přepis selže, řádek nepřidávej. Nahrávku ani přepis necommituj.

## Co z přepisu vytáhnout

Z každé epizody vytáhni jen to, co v ní zaznělo. U každé položky uveď pořad, název dílu a čas `mm:ss`. Jméno, klub, částku a důvod nech jen tehdy, když zazněly. Nejisté jméno označ `[nejisté]`. Prázdnou skupinu napiš jako „Nezaznělo.“

- **Kluby, dobrá finanční situace.** Řekli, že klub má peníze, vyrovnaný rozpočet, bohatého vlastníka, splacené dluhy nebo prostor nakupovat.
- **Kluby, špatná finanční situace.** Řekli, že klub má dluhy, problém s finančním fair play, nucený prodej, srážky mezd, insolvenci nebo že na nákup nemá.
- **Hráči, kteří hrají dobře.** Jméno a důvod: forma, zápas, góly, přihrávky, nasazení.
- **Hráči, kteří hrají špatně.** Jméno a důvod: forma, chyba, zranění, mimo sestavu, trest.
- **Mladí hráči.** Koho označili za mladého, talent, odchovance nebo dorostence a proč o něm mluví.
- **Nabídky na hráče.** Kdo nabízí, na koho, z jakého klubu a kam. Částku uveď jen když zazněla. Rozliš, jestli mluví o nabídce, zájmu, nebo o hotovém přestupu.

Přestup nebo spekulaci sám nepřeřazuj do finanční situace klubu. Do financí patří jen výrok, který o penězích klubu opravdu mluví. Údaje jsou z nahrávky, ne ověřený stav klubu.

Týdenní zpráva má nejdřív výtah po dílech. Stejná jména z víc pořadů nech u sebe a u každé zmínky uveď, ze kterého dílu je.

## Souhrn za zemi

Za týdenní průchod přidej ještě jeden celkový souhrn za každou zemi. Země ber ze skupin v `sledovane.txt`: Finsko, Norsko, Švédsko. Do souhrnu země patří všechny její nové díly z tohoto týdne.

Pořad ve skupině „Norsko a Švédsko“ rozděl podle toho, o které zemi se mluví. Věta o norském klubu patří do Norska, věta o švédském klubu do Švédska. Když věta bere obě země najednou, uveď ji v obou souhrnech.

Každý souhrn země má stejných šest skupin. Stejný klub nebo hráč ať je v jedné skupině jen jednou. Když se pořady liší, nech oba výroky a uveď pořad i díl. Nic nového oproti dílům nepřidávej. Když země ten týden nemá nový díl, napiš to a šest skupin nevyplňuj z dřívějších týdnů.

## Výstup pro uživatele

- Které díly byly tento týden nové, a které se přeskočily, protože už jsou v `zpracovane.txt`.
- Šest skupin po dílech. U jedné vložené epizody stejných šest skupin, bez souhrnu za zemi.
- U týdenního průchodu navíc celkový souhrn za Finsko, Norsko a Švédsko.
- Podmínky, výjimky a nejasnosti zmíněné v audiu.
- Úplný přepis jen na vyžádání.

## Slack

Veřejný kanál `#prepis-audia` (`C0C78B1UKBK`) je vyhrazený jen tomuto skillu. Když tě spustí zpráva z tohoto kanálu a je v ní audio nebo odkaz na podcast, spusť celý postup automaticky. Na další zadání nečekej. Ve zprávě stačí nahrávka nebo odkaz; uživatel nemusí psát, co z nich chce. Jiný úkol odmítni jednou větou a požádej o nahrávku nebo odkaz.

Odpověz ve vlákně té zprávy, která tě zavolala. České shrnutí pošli tam. Úplný přepis do Slacku nedávej, pokud o něj výslovně nepožádá.

- Mimo tento kanál ber cílový kanál jen ze zadání. Když kanál neuvede, ulož koncept do jeho vlastní přímé zprávy, ať text před odesláním vidí.
- Do jiného pojmenovaného kanálu zprávu odešli rovnou jen tehdy, když o odeslání výslovně požádá.
- Text piš běžným markdownem. Nejdřív které díly jsou ve zprávě, pak šest skupin po dílech: finance klubů, hráči ve formě, hráči mimo formu, mladí hráči, nabídky. U týdenního průchodu potom celkový souhrn za Finsko, za Norsko a za Švédsko. Nakonec nejasnosti.
- Do zprávy nepiš klíč k přepisu, cestu k nahrávce ani nic, co v audiu nezaznělo.
- Kód v repozitáři neměň a pull request nezakládej, pokud o to uživatel ve stejné zprávě výslovně nepožádá.

Do git commitu nepatří nahrávka, váhy modelu ani soubory z dočasné složky přepisu.
