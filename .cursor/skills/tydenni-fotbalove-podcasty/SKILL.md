---
name: tydenni-fotbalove-podcasty
description: >-
  Jednou týdně projde všechny fotbalové podcasty ze sledovane.txt. U každého
  pořadu ověří, že nejnovější nezpracovaný díl jde stáhnout přes PodscriptAPI,
  stáhne jeho přepis a uloží ho do repozitáře. Z textů toho běhu udělá jen
  český souhrn za Finsko, Norsko, Švédsko a Španělsko a ten soubor také uloží
  do repozitáře. Samostatný přehled dílů ani úplný přepis do odpovědi nedává.
  Audio nestahuje. Použij, když uživatel požádá o týdenní průchod, sledované
  podcasty nebo souhrn zemí. Jeden soubor nebo jeden odkaz na díl patří
  skillu prepis-audio.
---

# Týdenní fotbalové podcasty

Jednou týdně projdi všechny pořady ze seznamu. Nejdřív ověř, že díl jde stáhnout přes PodscriptAPI, pak ulož jeho text do repozitáře. Z textů toho běhu udělej jen souhrn zemí v češtině a ten soubor také ulož do repozitáře. Samostatný přehled jednotlivých dílů se nedělá. Úplný přepis do odpovědi nepatří. Audio se na tomto stroji nestahuje.

## Postup

1. Vezmi všechny adresy feedů ze [sledovane.txt](sledovane.txt). Skupina země je na řádku s `#`.
2. U každého pořadu vezmi nejnovější díl. Když už je ve [zpracovane.txt](zpracovane.txt), PodscriptAPI nevolej.
3. Jinak ověř přes PodscriptAPI, že podcast jde stáhnout. Když ne, díl přeskoč. Do souhrnu ho neber a do `zpracovane.txt` ho nezapisuj.
4. Když ověření projde, stáhni přepis a ulož ho do [texty](texty) v tomto skillu.
5. Z uložených textů tohoto běhu udělej jen souhrn za Finsko, Norsko, Švédsko a Španělsko v češtině. Souhrn ulož do [souhrny](souhrny) a soubor commitni.

Ber jen nejnovější díl každého pořadu. Starší díly ze stejného feedu v jednom běhu nepřepisuj. Jeden přiložený soubor nebo jeden odkaz na díl zpracuj skillem `prepis-audio`, ne tímto.

## Seznam

Jeden odkaz na řádek. Řádky s `#` a prázdné řádky přeskoč. Sledují se pořady s pravidelnými díly. Mezera mezi díly i zpoždění posledního dílu může být až měsíc, a pořad v souboru se bere i tak. Pořad podle názvu nevyhledávej. Když v souboru není žádný odkaz, zastav se a napiš, že seznam je prázdný.

Když uživatel pošle OPML, přepiš `sledovane.txt` adresami z `xmlUrl`. Název pořadu a skupinu nech na řádcích s `#`. Jiné pořady nepřidávej.

V `zpracovane.txt` je jeden `media_url` na řádek. Nejnovější díl s touto adresou přeskoč. Řádek tam dopiš až po uložení českého souhrnu, a jen u dílu, jehož text leží v `texty`. Když podcast nejde stáhnout, přepis chybí nebo ještě běží, řádek nepřidávej. Klíč necommituj.

## Stažení přepisu

Pořady ber jeden po druhém. U každého feedu spusť:

```bash
WEEKLY_DIR="<kořen tohoto skillu>"

python3 "$WEEKLY_DIR/scripts/fetch_transcript.py" \
  ODKAZ_ZE_SEZNAMU \
  --output-dir "$WEEKLY_DIR/texty" \
  --processed-file "$WEEKLY_DIR/zpracovane.txt" \
  --jobs-file "$WEEKLY_DIR/probihajici.txt"
```

Přepis dělá PodscriptAPI. Klíč je v prostředí jako `PODSCRIPT_API_KEY` a posílá se jako `Authorization: Bearer`. Klíč nevypisuj, nezapisuj do souboru a necommituj. Když klíč chybí, zastav se a přepis nespouštěj.

Před přepisem skript zavolá `GET /v1/lookup?url=<feed>`. Ověření stojí 1 kredit. `status: unavailable` znamená, že podcast přes PodscriptAPI nejde stáhnout. V tom případě se `POST` na přepis nespouští, souhrn se z dílu nedělá a díl se nezapisuje.

Když ověření projde, skript pošle `POST https://podscriptapi.com/api/v1/transcripts` s adresou feedu a `episode.guid` nejnovějšího dílu. Když díl `guid` nemá, pošle `episode.title`. Odpověď `200` je hotový přepis. Odpověď `202` znamená, že přepis běží: stejné `job_id` se dotahuje přes `GET /v1/transcripts/:id?format=json`. Tento GET je zdarma. Druhý `POST` na stejný díl nespouštěj, stojí dalších 15 kreditů. Jeden přepis stojí 15 kreditů bez ohledu na délku.

`status: saved` znamená, že text s časy `[mm:ss]` leží v `texty` a cesta je v `path`. To je podklad pro souhrn. Do odpovědi ho nekopíruj. `status: processed` znamená, že nejnovější díl už byl uložený. `status: processing` znamená, že PodscriptAPI ještě přepisuje; `job_id` zůstane v `probihajici.txt` a příští běh ho jen stáhne. `status: missing` znamená, že přepis není. Souhrn z toho dílu nevymýšlej a díl do `zpracovane.txt` nezapisuj.

Na jeden díl skript čeká nejvýš osm minut. U odpovědi `429` nečeká na dlouhý `Retry-After` a druhý přepis nespouští. Jiný zdroj přepisu nehledej. Audio nestahuj a místní přepis na tomto stroji nespouštěj. `probihajici.txt` necommituj. Nové soubory v `texty` commitni spolu se souhrnem.

Přepis zůstává v původním jazyce. Jméno, klub, částku a důvod nech jen tehdy, když jsou v textu. Nic nedoplňuj odhadem. U zdroje `asr` ber jména jako přepis řeči: nejisté označ `[nejisté]`.

## Souhrn zemí

Z textů uložených v tomto běhu napiš jen souhrn za Finsko, Norsko, Švédsko a Španělsko. Samostatný přehled dílu nevytvářej. Skupiny jsou v `sledovane.txt`. Do souhrnu země patří jen to, co zaznělo v textech tohoto běhu.

Souhrn je v češtině a drží se těchto oblastí. Prázdnou oblast nezobrazuj.

- **Finance klubů.** Finanční možnosti, problémy, potřeba prodávat nebo prostor pro posily.
- **Výkony hráčů.** Dobrá či špatná forma, konkrétní výkony, změna role nebo místa v sestavě.
- **Mladí hráči.** Talenti, kteří dostávají příležitost nebo na sebe upozorňují.
- **Přestupy a dostupnost.** Zájem, nabídky, dokončené přestupy a možné odchody.
- **Další důležité informace.** Zranění, tresty, vztahy s trenérem nebo situace v klubu.

U každé informace napiš, koho se týká, co zaznělo, v kterém pořadu a dílu, a čas `mm:ss`. Případný scoutingový závěr jasně odděl od toho, co řekli v podcastu.

Relevantní je liga a klub ze skupiny pořadu. U severského pořadu nech cizí ligu jen s vazbou na severský klub nebo hráče. U pořadu ze skupiny Španělsko nech španělskou ligu a španělský klub. Vynech reklamy, sázky, opakování a obecné řeči.

Pořad ve skupině „Norsko a Švédsko“ rozděl podle toho, o které zemi se mluví. Věta o obou zemích patří do obou souhrnů. Stejný klub nebo hráč ať je v jedné zemi jen jednou. Když se pořady liší, nech oba výroky a uveď pořad i díl. Nic nového oproti uloženým textům nepřidávej. Když země v tomto běhu nemá nový text, napiš to a souhrn nevyplňuj ze starších souborů.

Nevymýšlej jména, částky ani souvislosti. Nejisté jméno označ `[nejisté]` a neopravuj ho podle toho, koho znáš. Názor moderátora prezentuj jako názor, přestupový zájem jako zájem a vzpomínku jako historickou informaci. Přepis není nezávislé ověření.

Citaci v původním jazyce dej do souhrnu jen tehdy, když přesné znění pomáhá pochopit důležitou informaci.

## Uložení souhrnu

Souhrn v češtině ulož jako nový soubor:

`souhrny/RRRR-MM-DD-HHMM.md`

Čas je čas dokončení běhu. Starší souhrn nepřepisuj. V souboru jsou čtyři části: Finsko, Norsko, Švédsko, Španělsko. Stejný text patří do odpovědi.

Po uložení commitni tento soubor, nové soubory v `texty` a doplněné řádky v `zpracovane.txt`. Commit pushni do aktuální větve. Klíč ani `probihajici.txt` do commitu nedávej.

## Výstup

- Které díly se v tomto běhu stáhly, které už byly uložené a které podcasty PodscriptAPI nestáhne.
- Souhrn zemí v češtině, stejný jako soubor v `souhrny`.
- Nejasnosti.
- Cesta k uloženému souhrnu.
- Úplný přepis ani přehled jednotlivých dílů do odpovědi nepatří.

Ve Slacku odpověz ve vlákně, které tě zavolalo. Když kanál neuvede, ulož koncept do jeho vlastní přímé zprávy. Kód neměň a pull request nezakládej, pokud o to ve stejné zprávě nepožádá.
