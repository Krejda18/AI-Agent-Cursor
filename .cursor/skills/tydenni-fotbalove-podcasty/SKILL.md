---
name: tydenni-fotbalove-podcasty
description: >-
  Jednou týdně projde sledované fotbalové podcasty z sledovane.txt, najde
  celý textový přepis nových dílů a jazykovým modelem z něj česky vytáhne
  finance klubů, hráče a názory na jejich výkon, mladé hráče a nabídky.
  Nakonec udělá souhrn za Finsko, Norsko a Švédsko. Audio nestahuje. Použij,
  když uživatel požádá o týdenní průchod, sledované podcasty nebo souhrn zemí.
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

Už přepsané díly jsou v [zpracovane.txt](zpracovane.txt), jeden `media_url` na řádek. Ty přeskoč.

## Text místo audia

Celé audio se nestahuje a faster-whisper se nespouští. U každého dílu z posledních 7 dní se hledá celý přepis v textu.

```bash
PREPIS_DIR="<kořen skillu prepis-audio>"
WEEKLY_DIR="<kořen tohoto skillu>"
WORK_DIR="${TMPDIR:-/tmp}/tydenni-fotbalove-podcasty"
PYTHON="$PREPIS_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then PYTHON=python3; fi

"$PYTHON" "$WEEKLY_DIR/scripts/fetch_transcript.py" \
  ODKAZ_ZE_SEZNAMU \
  --output-dir "$WORK_DIR/transcripts" \
  --recent-days 7
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

`status: saved` je celý text s časy `[mm:ss]`. Prázdné pole znamená, že tento týden nový díl nevyšel. `status: missing` znamená, že text není. Ten díl do výtahu nepatří a do `zpracovane.txt` se nezapisuje, aby to šlo zkusit znovu. Audio se nedotahuje.

Až text existuje, dopiš `media_url` do `zpracovane.txt`. Když stažení textu selže, řádek nepřidávej. Text ani klíč necommituj.

Přepis zůstává v původním jazyce. Jméno, klub, částku a důvod nech jen tehdy, když jsou v textu. Nic nedoplňuj odhadem.

## Výtah jazykovým modelem

Souhrn dělá jazykový model z celého textu. Model na rozpoznání řeči se na souhrn nepoužívá.

Nejdřív díl zařaď jednou větou: aktuální kolo, rozhovor o kariéře, reprezentace, nebo jiný pořad. Rozhovor o minulosti není zpráva o tomto týdnu. Když v něm panel hodnotí, jak hráč hraje teď, ta věta do výtahu patří.

Hráči a názory na jejich výkon jsou hlavní část přehledu. Projdi celý text a ber každého hráče, kterého panel hodnotí. Recenze kola, sestavy nebo zápasu má často řadu jmen za sebou. Každý z nich s názorem na výkon dostane vlastní kartičku. Nezastavuj se u nejznámějšího jména v bloku a nezastavuj se po dvou nebo třech hráčích na díl.

Kartička:

- čas `mm:ss`
- skupina: finance-dobré, finance-špatné, forma-dobrá, forma-špatná, mladý, nabídka
- hráč nebo klub tak, jak je v citaci
- citace v původním jazyce, jedna až dvě věty, ve kterých je jméno a názor
- česky jedna až dvě věty: co si o jeho výkonu myslí
- druh: aktuální, vzpomínka, názor panelu, nejisté

Názor na výkon stačí v jedné větě. Patří sem, že hraje dobře nebo špatně, že je ostřejší, neviditelný, rozhodující nebo chybující, že má nastupovat, že ztratil místo, že potřebuje minuty, že je lepší nebo horší než spoluhráč, nebo že kvůli formě patří do reprezentace. Když se hosté neshodnou, nech oba názory jako dvě kartičky.

Jméno hráče musí být v citaci nebo ve stejné replice těsně kolem ní. Klub a částka jsou povinné jen u financí a u nabídky. Kartičku o výkonu nezahazuj proto, že v ní není gól, částka ani věta o penězích klubu.

Kartičku zahoď, když nejde poznat, o kom mluví, když je to reklama nebo sázka, když jde o cizí ligu bez vazby na severský klub, nebo když je jméno zkomolené a v textu se podruhé neopakuje. Samotné jméno bez názoru na výkon, peníze nebo nabídku kartička není. Nejisté jméno nech `[nejisté]` a neopravuj ho podle toho, koho znáš.

Do českého přehledu dej kartičky druhu aktuální a názor panelu. Vzpomínku dej stranou jako starou kariéru, pokud v ní není současný výkon. Když díl nemá ani jednu kartičku, napiš „Z tohoto dílu nešel použít výtah.“ Šest prázdných nadpisů nevyplňuj.

Skupiny, které kartičky pokryjí, vypiš pod dílem. U hráče uveď pořad, název dílu a čas `mm:ss`. Vyjmenuj hráče, které panel hodnotil. Nevybírej vzorek.

- **Kluby, dobrá finanční situace.** Řekli, že klub má peníze, vyrovnaný rozpočet, bohatého vlastníka, splacené dluhy nebo prostor nakupovat.
- **Kluby, špatná finanční situace.** Řekli, že klub má dluhy, problém s finančním fair play, nucený prodej, srážky mezd, insolvenci nebo že na nákup nemá.
- **Hráči, kteří hrají dobře.** Jméno, klub pokud zazněl, a názor na výkon: forma, zápas, góly, přihrávky, nasazení, role, srovnání se spoluhráčem nebo proč ho panel chválí.
- **Hráči, kteří hrají špatně.** Jméno, klub pokud zazněl, a názor na výkon: forma, chyba, ztráta místa, málo minut, zranění nebo trest, pokud kvůli tomu teď nehraje nebo hraje hůř.
- **Mladí hráči.** Koho označili za mladého, talent, odchovance nebo dorostence, jak si podle panelu teď vede a proč o něm mluví.
- **Nabídky na hráče.** Kdo nabízí, na koho, z jakého klubu a kam. Částku uveď jen když zazněla. Rozliš nabídku, zájem a hotový přestup. Když k nabídce zazní i názor na výkon, nech ho u stejného hráče.

Přestup sám nepřeřazuj do finanční situace klubu. Do financí patří jen výrok o penězích klubu. Údaje jsou z textu přepisu, ne ověřený stav klubu.

## Souhrn za zemi

Po výtahu dílů přidej celkový souhrn za Finsko, Norsko a Švédsko. Do souhrnu země patří kartičky z jejích nových textů tohoto týdne. Skupiny jsou v `sledovane.txt`.

Pořad ve skupině „Norsko a Švédsko“ rozděl podle toho, o které zemi se mluví. Věta o obou zemích patří do obou souhrnů. Do souhrnu dej všechny hráče z kartiček tohoto týdne, ne jen nejčastěji skloňované. Stejný hráč může být ve skupině víckrát, když se názory na jeho výkon liší. U každého výroku uveď pořad a díl. Když se pořady shodují, stačí jeden řádek a oba pořady. Nic nového oproti dílům nepřidávej. Když země ten týden nemá nový díl, napiš to a skupiny nevyplňuj z dřívějších týdnů.

## Výstup

- Které díly jsou nové, které se přeskočily a u kterých textový přepis chybí.
- Skupiny, které kartičky pokryjí. U hráčů vypiš jméno a názor na výkon, ne jen výčet jmen.
- Celkový souhrn za Finsko, za Norsko a za Švédsko.
- Nejasnosti.
- Úplný přepis jen na vyžádání.

Ve Slacku odpověz ve vlákně, které tě zavolalo. Když kanál neuvede, ulož koncept do jeho vlastní přímé zprávy. Kód neměň a pull request nezakládej, pokud o to ve stejné zprávě nepožádá.
