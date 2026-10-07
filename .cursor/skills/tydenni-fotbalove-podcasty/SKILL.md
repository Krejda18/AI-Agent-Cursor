---
name: tydenni-fotbalove-podcasty
description: >-
  Jednou týdně projde všechny fotbalové podcasty ze sledovane.txt. U každého
  pořadu stáhne přepis nejnovějšího nezpracovaného dílu přes PodscriptAPI a
  z něj udělá jen český scoutingový přehled: finance klubů, výkony hráčů,
  mladé hráče, přestupy a další situace v klubu. Úplný přepis do odpovědi
  nedává. Nakonec udělá souhrn za Finsko, Norsko, Švédsko a Španělsko. Audio
  nestahuje. Použij, když uživatel požádá o týdenní průchod, sledované
  podcasty nebo souhrn zemí. Jeden soubor nebo jeden odkaz na díl patří
  skillu prepis-audio.
---

# Týdenní fotbalové podcasty

Jednou týdně projdi všechny pořady ze seznamu. Nejdřív u nich stáhni přepis přes PodscriptAPI a z každého přepisu udělej jen shrnutí. Úplný přepis do odpovědi nepatří. Audio se na tomto stroji nestahuje.

## Postup

1. Vezmi všechny adresy feedů ze [sledovane.txt](sledovane.txt). Skupina země je na řádku s `#`.
2. U každého pořadu vezmi nejnovější díl. Když už je ve [zpracovane.txt](zpracovane.txt), PodscriptAPI nevolej. Jinak stáhni jeho přepis přes PodscriptAPI.
3. Z každého staženého přepisu udělej jen český scoutingový přehled. Celý přepis nevypisuj.
4. Ze stejných přehledů udělej souhrn za Finsko, Norsko, Švédsko a Španělsko.

Ber jen nejnovější díl každého pořadu. Starší díly ze stejného feedu v jednom běhu nepřepisuj. Jeden přiložený soubor nebo jeden odkaz na díl zpracuj skillem `prepis-audio`, ne tímto.

## Seznam

Jeden odkaz na řádek. Řádky s `#` a prázdné řádky přeskoč. Sledují se pořady s pravidelnými díly. Mezera mezi díly i zpoždění posledního dílu může být až měsíc, a pořad v souboru se bere i tak. Pořad podle názvu nevyhledávej. Když v souboru není žádný odkaz, zastav se a napiš, že seznam je prázdný.

Když uživatel pošle OPML, přepiš `sledovane.txt` adresami z `xmlUrl`. Název pořadu a skupinu nech na řádcích s `#`. Jiné pořady nepřidávej.

V `zpracovane.txt` je jeden `media_url` na řádek. Nejnovější díl s touto adresou přeskoč. Řádek tam dopiš až po českém shrnutí. Když přepis chybí nebo ještě běží, řádek nepřidávej. Text přepisu ani klíč necommituj.

## Stažení přepisu

Pořady ber jeden po druhém. U každého feedu spusť:

```bash
WEEKLY_DIR="<kořen tohoto skillu>"
WORK_DIR="${TMPDIR:-/tmp}/tydenni-fotbalove-podcasty"

python3 "$WEEKLY_DIR/scripts/fetch_transcript.py" \
  ODKAZ_ZE_SEZNAMU \
  --output-dir "$WORK_DIR/transcripts" \
  --processed-file "$WEEKLY_DIR/zpracovane.txt" \
  --jobs-file "$WEEKLY_DIR/probihajici.txt"
```

Přepis dělá PodscriptAPI. Klíč je v prostředí jako `PODSCRIPT_API_KEY` a posílá se jako `Authorization: Bearer`. Klíč nevypisuj, nezapisuj do souboru a necommituj. Když klíč chybí, zastav se a přepis nespouštěj.

Skript pošle `POST https://podscriptapi.com/api/v1/transcripts` s adresou feedu a `episode.guid` nejnovějšího dílu. Když díl `guid` nemá, pošle `episode.title`. Odpověď `200` je hotový přepis. Odpověď `202` znamená, že přepis běží: stejné `job_id` se dotahuje přes `GET /v1/transcripts/:id?format=json`. Tento GET je zdarma. Druhý `POST` na stejný díl nespouštěj, stojí dalších 15 kreditů. Jeden přepis stojí 15 kreditů bez ohledu na délku.

`status: saved` znamená, že text s časy `[mm:ss]` leží v `path`. Ten soubor je podklad pro shrnutí. Do odpovědi ho nekopíruj. `status: processed` znamená, že nejnovější díl už shrnutý byl. `status: processing` znamená, že PodscriptAPI ještě přepisuje; `job_id` zůstane v `probihajici.txt` a příští běh ho jen stáhne. `status: missing` znamená, že přepis není. Shrnutí nevymýšlej a díl do `zpracovane.txt` nezapisuj.

Na jeden díl skript čeká nejvýš osm minut. U odpovědi `429` nečeká na dlouhý `Retry-After` a druhý přepis nespouští. Jiný zdroj přepisu nehledej. Audio nestahuj a místní přepis na tomto stroji nespouštěj. `probihajici.txt` necommituj.

Přepis zůstává v původním jazyce. Jméno, klub, částku a důvod nech jen tehdy, když jsou v textu. Nic nedoplňuj odhadem. U zdroje `asr` ber jména jako přepis řeči: nejisté označ `[nejisté]`.

## Výtah

Z každého staženého dílu vytvoř stručný scoutingový přehled v češtině. Dělá ho jazykový model z celého textu. Do odpovědi patří jen tento přehled.

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

Po přehledech dílů přidej souhrn za Finsko, Norsko, Švédsko a Španělsko. Do souhrnu země patří informace z přehledů tohoto běhu. Skupiny jsou v `sledovane.txt`. Stejné oblasti jako u dílu. Prázdnou oblast nezobrazuj.

Pořad ve skupině „Norsko a Švédsko“ rozděl podle toho, o které zemi se mluví. Věta o obou zemích patří do obou souhrnů. Stejný klub nebo hráč ať je v jedné skupině jen jednou. Když se pořady liší, nech oba výroky a uveď pořad i díl. Nic nového oproti dílům nepřidávej. Scoutingový závěr i tady odděl od toho, co řekli v podcastu. Když země v tomto běhu nemá nový přepis, napiš to a souhrn nevyplňuj ze starších zpracovaných dílů.

## Výstup

- U každého pořadu ze seznamu: který nejnovější díl se vzal, nebo že už je zpracovaný, nebo že přepis chybí či ještě běží.
- Scoutingový přehled jen u dílů, jejichž přepis se v tomto běhu stáhl.
- Souhrn za Finsko, za Norsko, za Švédsko a za Španělsko.
- Nejasnosti.
- Úplný přepis do odpovědi nepatří.

Ve Slacku odpověz ve vlákně, které tě zavolalo. Když kanál neuvede, ulož koncept do jeho vlastní přímé zprávy. Kód neměň a pull request nezakládej, pokud o to ve stejné zprávě nepožádá.
