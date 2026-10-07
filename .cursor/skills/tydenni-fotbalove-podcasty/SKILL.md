---
name: tydenni-fotbalove-podcasty
description: >-
  Jednou týdně projde sledované fotbalové podcasty z sledovane.txt. U každého
  pořadu vezme nejnovější díl, který ještě není zpracovaný a už má celý text,
  a jazykovým modelem z něj česky vytáhne
  finance klubů, hráče ve formě i mimo ni, mladé hráče a nabídky. Nakonec
  udělá souhrn za Finsko, Norsko, Švédsko a Španělsko. Audio nestahuje. Použij, když
  uživatel požádá o týdenní průchod, sledované podcasty nebo souhrn zemí.
  Jeden soubor nebo jeden odkaz na díl patří skillu prepis-audio.
---

# Týdenní fotbalové podcasty

Postup:
Kazdy tyden projit sledovane podcasty s odkazy na jejich stazeni
Udelat z nich transcript:

Abstahovat dulezite informace o:
Klubech, dobra finacni situace, spatna financni situace
Hracich kteri hrajou dobre
Hracich kteri hrajou spatne
Mlade hrace
Nabidkach na hrace

## Kdy skill použít

Spusť ho, když uživatel chce týdenní průchod sledovaných podcastů. Jeden přiložený soubor nebo jeden odkaz na díl zpracuj skillem `prepis-audio`, ne tímto.

## Seznam

Odkazy ke stažení jsou v [sledovane.txt](sledovane.txt). Jeden odkaz na řádek. Řádky s `#` a prázdné řádky přeskoč. Sledují se pořady s pravidelnými díly. Mezera mezi díly i zpoždění posledního dílu může být až měsíc. Pořad podle názvu nevyhledávej. Když v souboru není žádný odkaz, zastav se a napiš, že seznam je prázdný.

Když uživatel pošle OPML, přepiš `sledovane.txt` adresami z `xmlUrl`. Název pořadu a skupinu nech na řádcích s `#`. Jiné pořady nepřidávej.

Už zpracované díly jsou v [zpracovane.txt](zpracovane.txt), jeden `media_url` na řádek. Ty přeskoč. Řádek tam patří až po výtahu z celého textu.

## Text místo audia

Celé audio se nestahuje a faster-whisper se nespouští. U každého pořadu vezmi jeden díl: nejnovější, který ještě není v `zpracovane.txt` a už má celý text. Novější díl bez textu neber a nezapisuj ho, ať ho jde vzít, až přepis bude. Hledej 31 dní dozadu, protože sledovaný pořad může mít poslední díl až měsíc pozadu.

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

Skript u dílu zkusí v tomto pořadí:

1. `podcast:transcript` ve feedu, nebo odkaz na `.vtt`, `.srt`, `.ttml` či cestu s `transcript` v popisu dílu.
2. Stejný odkaz na stránce dílu.
3. Podscan, jen když je v prostředí `PODSCAN_API_KEY`. Díl se páruje podle RSS a `guid`, případně podle adresy audia. Stáhne se WebVTT. Klíč se nikam nezapisuje.

Jiné cesty u těchto pořadů celý text nedaly. Znovu je nezkoušej a kvůli nim nestahuj audio.

- Apple Podcasts má u nejnovějšího dílu všech 11 pořadů prázdné `transcriptInfo`. Soukromý bearer token se nepoužívá.
- Acast má u dílů pole `transcript`, ale je prázdné.
- Spotify přepis přes své API nevrací.
- YouTube má stejný díl u 90MinSvenskan, Studio Allsvenskan a Nordic Football Podcast. Titulky odtud nejdou stáhnout, přehrávač vrací kontrolu proti robotům a prázdný soubor titulků. Rabona, Napit Edellä a deník Fotbollsmorgon stejné video nemají. Video nehledej podle podobného názvu.

`status: saved` je celý text s časy `[mm:ss]` u dílu, který ještě nebyl zpracovaný. Prázdné pole znamená, že v okně 31 dní takový díl není. Díly bez textu skript nevrací a do `zpracovane.txt` se nezapisují. Audio se nedotahuje.

Až z textu vznikne výtah, dopiš `media_url` do `zpracovane.txt`. Když text chybí, řádek nepřidávej. Text ani klíč necommituj.

Přepis zůstává v původním jazyce. Jméno, klub, částku a důvod nech jen tehdy, když jsou v textu. Nic nedoplňuj odhadem.

## Výtah jazykovým modelem

Souhrn dělá jazykový model z celého textu. Model na rozpoznání řeči se na souhrn nepoužívá.

Nejdřív díl zařaď jednou větou: aktuální kolo, rozhovor o kariéře, reprezentace, nebo jiný pořad. Rozhovor o minulosti není zpráva o tomto týdnu.

Pak projdi text po blocích. Z každého bloku ber jen kartičku, u které zůstane citace:

- čas `mm:ss`
- skupina: finance-dobré, finance-špatné, forma-dobrá, forma-špatná, mladý, nabídka
- klub nebo hráč tak, jak je v citaci
- citace v původním jazyce, jedna až dvě věty
- česky jedna věta
- druh: aktuální, vzpomínka, názor panelu, nejisté

Kartičku zahoď, když v citaci chybí jméno, klub nebo částka, když je to reklama nebo sázka, nebo když je jméno zkomolené a v textu se podruhé neopakuje. U severského pořadu zahoď i cizí ligu bez vazby na severský klub. U pořadu ze skupiny Španělsko nech španělskou ligu a španělský klub. Nejisté jméno nech `[nejisté]` a neopravuj ho podle toho, koho znáš.

Do českého přehledu dej kartičky druhu aktuální a názor panelu. Vzpomínku dej stranou jako starou kariéru. Když díl nemá ani jednu kartičku, napiš „Z tohoto dílu nešel použít výtah.“ Šest prázdných nadpisů nevyplňuj.

Skupiny, které kartičky pokryjí, vypiš pod dílem. U položky uveď pořad, název dílu a čas `mm:ss`.

- **Kluby, dobrá finanční situace.** Řekli, že klub má peníze, vyrovnaný rozpočet, bohatého vlastníka, splacené dluhy nebo prostor nakupovat.
- **Kluby, špatná finanční situace.** Řekli, že klub má dluhy, problém s finančním fair play, nucený prodej, srážky mezd, insolvenci nebo že na nákup nemá.
- **Hráči, kteří hrají dobře.** Jméno a důvod: forma, zápas, góly, přihrávky, nasazení.
- **Hráči, kteří hrají špatně.** Jméno a důvod: forma, chyba, zranění, mimo sestavu, trest.
- **Mladí hráči.** Koho označili za mladého, talent, odchovance nebo dorostence a proč o něm mluví.
- **Nabídky na hráče.** Kdo nabízí, na koho, z jakého klubu a kam. Částku uveď jen když zazněla. Rozliš nabídku, zájem a hotový přestup.

Přestup sám nepřeřazuj do finanční situace klubu. Do financí patří jen výrok o penězích klubu. Údaje jsou z textu přepisu, ne ověřený stav klubu.

## Souhrn za zemi

Po výtahu dílů přidej celkový souhrn za Finsko, Norsko, Švédsko a Španělsko. Do souhrnu země patří kartičky z vybraných textů. Skupiny jsou v `sledovane.txt`.

Pořad ve skupině „Norsko a Švédsko“ rozděl podle toho, o které zemi se mluví. Věta o obou zemích patří do obou souhrnů. Stejný klub nebo hráč ať je v jedné skupině jen jednou. Když se pořady liší, nech oba výroky a uveď pořad i díl. Nic nového oproti dílům nepřidávej. Když země nemá vybraný díl, napiš to a skupiny nevyplňuj ze starších zpracovaných dílů.

## Výstup

- Který díl se vzal: ještě nebyl zpracovaný a má celý text. Když v okně 31 dní takový díl není, napiš to. Novější díl bez textu jen zmiň, že na něj text ještě není.
- Skupiny, které kartičky pokryjí.
- Celkový souhrn za Finsko, za Norsko, za Švédsko a za Španělsko.
- Nejasnosti.
- Úplný přepis jen na vyžádání.

Ve Slacku odpověz ve vlákně, které tě zavolalo. Když kanál neuvede, ulož koncept do jeho vlastní přímé zprávy. Kód neměň a pull request nezakládej, pokud o to ve stejné zprávě nepožádá.
