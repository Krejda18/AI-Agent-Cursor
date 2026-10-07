---
name: tydenni-fotbalove-podcasty
description: >-
  Jednou týdně projde sledované fotbalové podcasty z sledovane.txt. U každého
  pořadu vezme nejnovější díl, který ještě není zpracovaný a už má celý text,
  a jazykovým modelem z něj udělá český scoutingový přehled: finance klubů,
  výkony hráčů, mladé hráče, přestupy a další situace v klubu. Nakonec
  udělá souhrn za Finsko, Norsko, Švédsko a Španělsko. Audio nestahuje. Použij,
  když uživatel požádá o týdenní průchod, sledované podcasty nebo souhrn zemí.
  Jeden soubor nebo jeden odkaz na díl patří skillu prepis-audio.
---

# Týdenní fotbalové podcasty

Jednou týdně projdi sledované pořady a z hotového textu udělej český výtah. Audio se nestahuje a přepis se na tomto stroji nevytváří.

## Postup

1. Vezmi adresy feedů ze [sledovane.txt](sledovane.txt). Skupina země je na řádku s `#`.
2. U každého pořadu vyber jeden díl: nejnovější, který ještě není v [zpracovane.txt](zpracovane.txt) a už má celý text. Hledej 31 dní dozadu. Novější díl bez textu přeskoč a nezapisuj ho.
3. Z vybraného textu udělej stručný scoutingový přehled v češtině.
4. Ze stejných přehledů udělej souhrn za Finsko, Norsko, Švédsko a Španělsko.

Jeden přiložený soubor nebo jeden odkaz na díl zpracuj skillem `prepis-audio`, ne tímto.

## Seznam

Jeden odkaz na řádek. Řádky s `#` a prázdné řádky přeskoč. Sledují se pořady s pravidelnými díly. Mezera mezi díly i zpoždění posledního dílu může být až měsíc. Pořad podle názvu nevyhledávej. Když v souboru není žádný odkaz, zastav se a napiš, že seznam je prázdný.

Když uživatel pošle OPML, přepiš `sledovane.txt` adresami z `xmlUrl`. Název pořadu a skupinu nech na řádcích s `#`. Jiné pořady nepřidávej.

V `zpracovane.txt` je jeden `media_url` na řádek. Ty díly přeskoč. Řádek tam dopiš až po výtahu z celého textu. Když text chybí, řádek nepřidávej. Text ani klíč necommituj.

## Výběr dílu

```bash
PREPIS_DIR="<kořen skillu prepis-audio>"
WEEKLY_DIR="<kořen tohoto skillu>"
WORK_DIR="${TMPDIR:-/tmp}/tydenni-fotbalove-podcasty"
PYTHON="$PREPIS_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then PYTHON=python3; fi

"$PYTHON" "$WEEKLY_DIR/scripts/fetch_transcript.py" \
  ODKAZ_ZE_SEZNAMU \
  --output-dir "$WORK_DIR/transcripts" \
  --recent-days 31 \
  --ready-only \
  --processed-file "$WEEKLY_DIR/zpracovane.txt"
```

Skripty jsou ve skillu `prepis-audio` a v `scripts` tohoto skillu. Když v `PREPIS_DIR` není `.venv`, stačí `python3`.

Skript hledá hotový text v tomto pořadí:

1. `podcast:transcript` ve feedu, nebo odkaz na `.vtt`, `.srt`, `.ttml` či cestu s `transcript` v popisu dílu.
2. Stejný odkaz na stránce dílu.
3. Podscan, jen když je v prostředí `PODSCAN_API_KEY`. Díl se páruje podle RSS a `guid`, případně podle adresy audia. Stáhne se WebVTT. Klíč se nikam nezapisuje.

U severských pořadů už jiné cesty celý text nedaly. Znovu je nezkoušej a kvůli nim nestahuj audio.

- Apple Podcasts má u nejnovějšího dílu severských pořadů prázdné `transcriptInfo`. Soukromý bearer token se nepoužívá.
- Acast má u dílů pole `transcript`, ale je prázdné.
- Spotify přepis přes své API nevrací.
- YouTube má stejný díl u 90MinSvenskan, Studio Allsvenskan a Nordic Football Podcast. Titulky odtud nejdou stáhnout, přehrávač vrací kontrolu proti robotům a prázdný soubor titulků. Rabona, Napit Edellä a deník Fotbollsmorgon stejné video nemají. Video nehledej podle podobného názvu.

`status: saved` je celý text s časy `[mm:ss]` u dílu, který ještě nebyl zpracovaný. Prázdné pole znamená, že v okně 31 dní takový díl není. Díly bez textu skript nevrací. Audio se nedotahuje.

Přepis zůstává v původním jazyce. Jméno, klub, částku a důvod nech jen tehdy, když jsou v textu. Nic nedoplňuj odhadem.

## Výtah

Z každého vybraného dílu vytvoř stručný scoutingový přehled v češtině. Dělá ho jazykový model z celého textu. Model na rozpoznání řeči se na přehled nepoužívá.

Na začátku uveď pořad, název epizody, datum a jednou větou její hlavní téma. Rozliš aktuální dění od rozhovoru o minulosti.

Potom vypiš pouze relevantní informace v těchto oblastech:

- **Finance klubů.** Finanční možnosti, problémy, potřeba prodávat nebo prostor pro posily.
- **Výkony hráčů.** Dobrá či špatná forma, konkrétní výkony, změna role nebo místa v sestavě.
- **Mladí hráči.** Talenti, kteří dostávají příležitost nebo na sebe upozorňují.
- **Přestupy a dostupnost.** Zájem, nabídky, dokončené přestupy a možné odchody.
- **Další důležité informace.** Zranění, tresty, vztahy s trenérem nebo situace v klubu.

U každé informace napiš, koho se týká, co zaznělo a jaký to může mít význam pro scouting. Připoj čas v epizodě `mm:ss`, aby šel výrok dohledat. Případný scoutingový závěr jasně odděl od toho, co řekli v podcastu.

Relevantní je liga a klub ze skupiny pořadu ve `sledovane.txt`. U severského pořadu nech cizí ligu jen s vazbou na severský klub nebo hráče. U pořadu ze skupiny Španělsko nech španělskou ligu a španělský klub. Vynech reklamy, sázky, opakování a obecné řeči. Prázdné oblasti nezobrazuj. Když díl nemá ani jednu informaci, napiš „Z tohoto dílu nešel použít výtah.“

Nevymýšlej jména, částky ani souvislosti. Nejisté jméno označ `[nejisté]` a neopravuj ho podle toho, koho znáš. Názor moderátora prezentuj jako názor, přestupový zájem jako zájem a vzpomínku jako historickou informaci. Přepis není nezávislé ověření.

Citace v původním jazyce uchovej jako podklad. Do hlavního přehledu ji dej jen tehdy, když přesné znění pomáhá pochopit důležitou informaci.

## Souhrn zemí

Po přehledech dílů přidej souhrn za Finsko, Norsko, Švédsko a Španělsko. Do souhrnu země patří informace z vybraných textů. Skupiny jsou v `sledovane.txt`. Stejné oblasti jako u dílu. Prázdnou oblast nezobrazuj.

Pořad ve skupině „Norsko a Švédsko“ rozděl podle toho, o které zemi se mluví. Věta o obou zemích patří do obou souhrnů. Stejný klub nebo hráč ať je v jedné skupině jen jednou. Když se pořady liší, nech oba výroky a uveď pořad i díl. Nic nového oproti dílům nepřidávej. Scoutingový závěr i tady odděl od toho, co řekli v podcastu. Když země nemá vybraný díl, napiš to a souhrn nevyplňuj ze starších zpracovaných dílů.

## Výstup

- Který díl se vzal: ještě nebyl zpracovaný a má celý text. Když v okně 31 dní takový díl není, napiš to. Novější díl bez textu jen zmiň, že na něj text ještě není.
- Scoutingový přehled dílu.
- Souhrn za Finsko, za Norsko, za Švédsko a za Španělsko.
- Nejasnosti.
- Úplný přepis jen na vyžádání.

Ve Slacku odpověz ve vlákně, které tě zavolalo. Když kanál neuvede, ulož koncept do jeho vlastní přímé zprávy. Kód neměň a pull request nezakládej, pokud o to ve stejné zprávě nepožádá.
