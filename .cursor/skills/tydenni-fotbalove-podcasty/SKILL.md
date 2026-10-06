---
name: tydenni-fotbalove-podcasty
description: >-
  Jednou týdně projde sledované fotbalové podcasty z sledovane.txt, stáhne
  nové díly, přepíše je a česky vytáhne finance klubů, hráče ve formě i mimo
  ni, mladé hráče a nabídky. Nakonec udělá souhrn za Finsko, Norsko a Švédsko.
  Použij, když uživatel požádá o týdenní průchod, sledované podcasty nebo
  souhrn zemí. Jeden soubor nebo jeden odkaz na díl patří skillu prepis-audio.
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

Odkazy ke stažení jsou v [sledovane.txt](sledovane.txt). Jeden odkaz na řádek. Řádky s `#` a prázdné řádky přeskoč. Pořad podle názvu nevyhledávej. Když v souboru není žádný odkaz, zastav se a napiš, že seznam je prázdný.

Když uživatel pošle OPML, přepiš `sledovane.txt` adresami z `xmlUrl`. Název pořadu a skupinu nech na řádcích s `#`. Jiné pořady nepřidávej.

Už přepsané díly jsou v [zpracovane.txt](zpracovane.txt), jeden `media_url` na řádek. Ty přeskoč.

## Stažení a přepis

Skripty jsou ve skillu `prepis-audio`. Jeho složku najdi jako sourozence `../prepis-audio` nebo jako `.cursor/skills/prepis-audio`.

```bash
PREPIS_DIR="<kořen skillu prepis-audio>"
WORK_DIR="${TMPDIR:-/tmp}/tydenni-fotbalove-podcasty"
```

Když v `PREPIS_DIR` není `.venv`, založ ho podle skillu `prepis-audio`.

Pro každý odkaz stáhni díly z posledních 7 dní:

```bash
"$PREPIS_DIR/.venv/bin/python" "$PREPIS_DIR/scripts/fetch_audio.py" \
  ODKAZ_ZE_SEZNAMU \
  --output-dir "$WORK_DIR/audio" \
  --recent-days 7
```

`feed_recent` jsou díly s datem v posledních 7 dnech. `feed_latest` znamená, že feed datum nemá, takže je stažený jen nejnovější díl; ve zprávě to napiš. Prázdné pole znamená, že tento týden nový díl nevyšel.

Každý nový soubor přepiš celý skriptem `transcribe.py` ze skillu `prepis-audio`, výstup do `$WORK_DIR/transcripts`. Až přepis existuje, dopiš jeho `media_url` do `zpracovane.txt`. Když přepis selže, řádek nepřidávej. Nahrávku ani přepis necommituj.

Přepis je v původním jazyce, s časy. Nesrozumitelné místo nech `[nesrozumitelné]`, nejisté `[nejisté]`. Jméno, klub, částku a důvod nech jen tehdy, když zazněly. Nic nedoplňuj odhadem.

## Výtah z dílu

Z každého nového dílu vytáhni šest skupin. U položky uveď pořad, název dílu a čas `mm:ss`. Prázdnou skupinu napiš jako „Nezaznělo.“

- **Kluby, dobrá finanční situace.** Řekli, že klub má peníze, vyrovnaný rozpočet, bohatého vlastníka, splacené dluhy nebo prostor nakupovat.
- **Kluby, špatná finanční situace.** Řekli, že klub má dluhy, problém s finančním fair play, nucený prodej, srážky mezd, insolvenci nebo že na nákup nemá.
- **Hráči, kteří hrají dobře.** Jméno a důvod: forma, zápas, góly, přihrávky, nasazení.
- **Hráči, kteří hrají špatně.** Jméno a důvod: forma, chyba, zranění, mimo sestavu, trest.
- **Mladí hráči.** Koho označili za mladého, talent, odchovance nebo dorostence a proč o něm mluví.
- **Nabídky na hráče.** Kdo nabízí, na koho, z jakého klubu a kam. Částku uveď jen když zazněla. Rozliš nabídku, zájem a hotový přestup.

Přestup sám nepřeřazuj do finanční situace klubu. Do financí patří jen výrok o penězích klubu. Údaje jsou z nahrávky, ne ověřený stav klubu.

## Souhrn za zemi

Po výtahu dílů přidej celkový souhrn za Finsko, Norsko a Švédsko. Do souhrnu země patří všechny její nové díly z tohoto týdne. Skupiny jsou v `sledovane.txt`.

Pořad ve skupině „Norsko a Švédsko“ rozděl podle toho, o které zemi se mluví. Věta o obou zemích patří do obou souhrnů. Stejný klub nebo hráč ať je v jedné skupině jen jednou. Když se pořady liší, nech oba výroky a uveď pořad i díl. Nic nového oproti dílům nepřidávej. Když země ten týden nemá nový díl, napiš to a skupiny nevyplňuj z dřívějších týdnů.

## Výstup

- Které díly jsou nové a které se přeskočily.
- Šest skupin po dílech.
- Celkový souhrn za Finsko, za Norsko a za Švédsko.
- Nejasnosti.
- Úplný přepis jen na vyžádání.

Ve Slacku odpověz ve vlákně, které tě zavolalo. Když kanál neuvede, ulož koncept do jeho vlastní přímé zprávy. Kód neměň a pull request nezakládej, pokud o to ve stejné zprávě nepožádá.
