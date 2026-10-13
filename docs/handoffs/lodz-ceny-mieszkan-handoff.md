# Handoff: warstwy cen mieszkań w Łodzi

Data rozpoznania: 2026-10-06. Cel: dwie warstwy GIS dla Łodzi.

1. Ceny historyczne, transakcje z aktu notarialnego. Źródło: krajowy Rejestr Cen Nieruchomości (RCN) GUGiK.
2. Ceny oferowane, lokale wystawione przez deweloperów. Źródło: dzienne cenniki na dane.gov.pl, API 1.4.

Nie mieszaj tych warstw. RCN to cena zapłacona, zwykle z opóźnieniem. API deweloperów to cena z cennika, bez geometrii, często niekompletna.

Istniejąca próbka Śródmieścia leży w `artifacts/rcn-lodz/`:

- `srodmiescie_lokale.csv` — 26433 lokale z WFS, TERYT 1061, surowe.
- `srodmiescie_mieszkania.geojson` — lokale mieszkalne po filtrze, EPSG:2180, oś w pliku już jako wschód/północ.
- `srodmiescie_cena_m2_rok.csv`, `srodmiescie_cena_m2_kwartal.csv` — mediany. Nie używaj ich jako trendu 2022–2024, patrz dziura niżej.
- `profbud_lodz_oferta_sample.csv` — jeden cennik, Primo IV, Lindleya 8.

## Warstwa 1. RCN, ceny z rynku

### Endpoint

Jedna usługa WMS i WFS, bez klucza, bez opłaty:

```
https://mapy.geoportal.gov.pl/wss/service/rcn
```

WFS 2.0.0. Warstwy:

- `ms:lokale` — to jest warstwa mieszkań
- `ms:budynki`
- `ms:dzialki`
- `ms:powiaty`

Układ: EPSG:2180. GetCapabilities:

```
https://mapy.geoportal.gov.pl/wss/service/rcn?service=WFS&version=2.0.0&request=GetCapabilities
```

Starsza integracja KICN nie ma kwoty. Nie używaj jej do cen:

```
https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaCenNieruchomosci
```

### Oś, bez tego bbox jest zły

W `bbox` i w GML kolejność to północ, potem wschód. Odwrotnie serwer zwraca obce powiaty (przy próbie Śródmieścia wpadł mogileński, TERYT 0409, adresy Bystrzyca i Czarnotul).

Łódź, miasto, prostokąt roboczy 19,30–19,64 E, 51,68–51,86 N:

```
bbox=423772,520735,443936,544060,urn:ogc:def:crs:EPSG::2180
```

Śródmieście, sprawdzone, 19,435–19,490 E, 51,745–51,790 N:

```
bbox=431046,530023,436073,533786,urn:ogc:def:crs:EPSG::2180
```

Jedna strona, 250 obiektów:

```
https://mapy.geoportal.gov.pl/wss/service/rcn?service=WFS&version=2.0.0&request=GetFeature&typeNames=ms:lokale&count=250&startIndex=0&bbox=431046,530023,436073,533786,urn:ogc:def:crs:EPSG::2180&outputFormat=application/gml+xml;%20version=3.2
```

Paginacja: atrybut `next` albo `startIndex` co 250. Przy Śródmieściu zeszło 106 stron, 26433 rekordy, wszystkie TERYT `1061`. Dla całego miasta idź tym samym wzorem, tylko większy bbox, i filtruj `TERYT=1061`. Nie ufaj bboxowi bez tego filtra.

QGIS: Warstwa, dodaj WFS, ten adres, warstwa `lokale`. WMS pokazuje obiekty dopiero od skali 1:5000.

### Pola, które brać

Z `DescribeFeatureType` dla `ms:lokale`:

- cena: `LOK_CENA_BRUTTO`, jak pusta to `TRAN_CENA_BRUTTO`
- metraż: `LOK_POW_UZYT`
- data aktu: `DOK_DATA`
- rynek: `TRAN_RODZAJ_RYNKU` (`rynekPierwotny`, `rynekWtorny`, często puste)
- typ transakcji: `TRAN_RODZAJ_TRANS` (`wolnyRynek`, `sprzedazZBonifikata`, `sprzedazBezprzetargowa`, często puste)
- funkcja: `LOK_FUNKCJA` — do warstwy mieszkań tylko `mieszkalna`
- izby, piętro: `LOK_LICZBA_IZB`, `LOK_NR_KOND`
- adres: `LOK_ADRES`, format `MSC:Łódź;UL:...;NR_PORZ:...`, często pusty
- udział: `NIER_UDZIAL`, bierz `1/1`
- powiat: `TERYT`, Łódź miasto = `1061`
- id: `TRAN_LOKALNY_ID_IIP`, `LOK_ID_LOKALU`, `gid`
- strony: `TRAN_SPRZEDAJACY`, `TRAN_KUPUJACY` to typ (`osobaFizyczna`), nie nazwisko
- notariusz zostaje: `DOK_TWORCA`, `DOK_OZNACZENIE`

Geometria w GML to punkt. Współrzędna w `<gml:pos>` jest północ wschód. Do GeoJSON zapisz jako wschód, północ.

### Filtr do warstwy

- `TERYT == 1061`
- `LOK_FUNKCJA == mieszkalna`
- metraż 25–120 m²
- cena / metraż w 2500–25000 zł
- udział pusty albo `1/1`
- wyrzuć `sprzedazZBonifikata`, `sprzedazBezprzetargowa`, `sprzedazPrzetargowa`
- deduplikuj po `TRAN_LOKALNY_ID_IIP` + `LOK_ID_LOKALU` + data + cena

Cena jednostkowa: `LOK_CENA_BRUTTO / LOK_POW_UZYT`, a jak cena lokalu pusta, `TRAN_CENA_BRUTTO / LOK_POW_UZYT`. Jeden akt potrafi dać kilka rekordów (lokal, udział w gruncie, garaż). Garaż ma `LOK_FUNKCJA=garaz`, nie wciągaj go do mediany mieszkań.

### Dziura w Łodzi

W pobranej paczce Śródmieścia daty aktów: gęsto 2010–2018, potem prawie nic, znowu od połowy 2025.

Mieszkalne w prostokącie: 2018 = 2614, 2019–2023 = praktycznie 0, 2024 = 35, 2025 = 747, 2026 do 2 września = 2538. To brak w eksporcie krajowym, nie pusty rynek. Nie licz trendu 2022–2024 z tego pliku. Jak warstwa ma mieć ciągłe lata, sprawdź GML powiatu na dane.gov.pl i eksport z modułu analiz cen na geoportal.gov.pl (XLSX/CSV, od 2026-09-23, 35 pól). Usługa WFS jest tymczasowa.

Median y po filtrze, tylko żeby wiedzieć rząd wielkości, nie jako gotowy wskaźnik:

- 2018: 4459 zł/m² (n=1768)
- 2025: 9671 (n=576)
- 2026: 10000 (n=2229)
- wtórny 2026: 7587 (n=747)
- pierwotny 2026: 10600 (n=1482)

Opóźnienie aktu: miesiące, przy nowym budynku do około dwóch lat.

## Warstwa 2. Oferty deweloperów

### API

Bez klucza, JSON:API.

```
https://api.dane.gov.pl/1.4/datasets
https://api.dane.gov.pl/1.4/institutions
https://api.dane.gov.pl/1.4/datasets/{id}/resources?per_page=5&sort=-data_date
```

Nagłówek: `Accept: application/vnd.api+json`.

Nie używaj `q=Łódź`. Szukanie tnie frazę i zwraca ~20 tys. zbiorów. Działa filtr tytułu:

```
https://api.dane.gov.pl/1.4/datasets?title=Łódź&per_page=100&page=1
https://api.dane.gov.pl/1.4/datasets?title=Łodzi&per_page=100&page=1
https://api.dane.gov.pl/1.4/datasets?keyword=deweloper&per_page=100&page=1
```

`title=Łódź` ma 254 zbiory, `keyword=deweloper` ma 387. Z tego cenniki z Łodzią w tytule to kilkanaście inwestycji plus kilkadziesiąt duplikatów Polnej 18.

Instytucje z Łodzią w nazwie, nie wszystkie budowy w mieście:

- 2760 Profbud Łódź
- 5865 ROBYG Łódź
- 849 Archicom Łódź 1
- 1298 ŻD Łódź Wróblewskiego
- 1299 ŻD Łódź Ustronna
- 6687 ŻD Łódź Kilińskiego

Zbiory instytucji:

```
https://api.dane.gov.pl/1.4/institutions/2760/datasets
```

Plik dnia jest w `file_url`, `csv_file_url` albo `download_url` zasobu. Jak puste, zasób nie ma pliku.

### Co jest w rekordzie

Wzorzec ministerstwa, około 60 kolumn. Bierz:

- miejscowość, ulica, numer, kod inwestycji (kolumny „lokalizacji przedsięwzięcia”)
- nazwa przedsięwzięcia
- numer lokalu nadany przez dewelopera
- powierzchnia użytkowa
- cena za m² i data, od której obowiązuje
- cena lokalu
- liczba izb, piętro, jeśli są

Nie ma lat/lon, nie ma identyfikatora działki, nie ma TERYT budynku. Cała inwestycja ma jeden adres tekstowy. Geokoduj ulicę i numer, przypnij wszystkie lokale do tego punktu. Heksagon dostanie cenę tylko tam, gdzie stoi opublikowana budowa.

Schemat nie jest wspólny. Widziane nazwy kolumny ceny:

- `Cena za m2 nieruchomości`
- `Cena m 2 powierzchni użytkowej lokalu mieszkalnego`
- `Cena brutto/m2 powierzchni produktu [zł]`
- `Cena za m² (PLN)`
- `Cena za m2`

Puste bywa zapisane jako `X`. Separator zwykle przecinek, czasem średnik. Ceny z przecinkiem dziesiętnym. Nie bierz pierwszej kolumny ze słowem „cena”: wpadnie cena lokalu albo data.

### Co dało się policzyć 2026-10-06

| Zbiór | Inwestycja | Rekordy | Z ceną m² | Mediana zł/m² | Data pliku |
|---:|---|---:|---:|---:|---|
| 5016 | Wróblewskiego 2/4 | 343 | 274 | 10000 | 2026-10-05 |
| 11485 | Ustronna | 212 | 114 | 9600 | 2026-10-06 |
| 39441 | Kilińskiego Square | 214 | 142 | 11800 | 2026-10-06 |
| 32194 | Archicom Łódź | 96 | 73 | 12239 | 2026-10-05 |
| 32195 | APL Ustronna | 37 | 37 | 9606 | 2026-10-06 |
| 26590 | Villa Bema | 3 | 3 | 10000 | — |
| 20696 | Primo IV, Lindleya 8 | 22 | cena m² pusta, cena lokalu jest (przykład 568333 zł) | — | 2026-09-01 |

Puste albo bez URL: 4863 Pogonowskiego 52, 4946 Pogonowskiego 73, 36323 Nowe Złotno VII, 18172 ROBYG Lira House, 12233 Ozorkowska 28, 12251 Targowa 49, 36570 Dream Park. Polna 18 jest wielokrotnie jako osobny zbiór (17500 i kolejne), plik bywał z NUL.

To nie jest pokrycie Łodzi. Deweloper z siedzibą poza miastem nie wpadnie, jeśli w tytule zbioru nie ma „Łódź”.

## Co zrobić

1. Dociągnij `ms:lokale` dla bboxu miasta, oś północ-wschód, filtr `TERYT=1061`.
2. Zostaw `mieszkalna`, policz zł/m², zapisz GeoJSON albo GPKG w EPSG:2180. Pole `zrodlo=rcn`, `rodzaj=transakcja`.
3. Oznacz lata 2019–2024 jako brak w eksporcie, nie jako zero transakcji.
4. Zbierz cenniki: `title=Łódź`, `title=Łodzi`, `keyword=deweloper`, plus instytucje 2760, 5865, 849, 1298, 1299, 6687. Bierz najnowszy zasób.
5. Znormalizuj kolumnę ceny m². Geokoduj adres inwestycji. Pole `zrodlo=dane.gov.pl`, `rodzaj=oferta`.
6. Dwie warstwy, nie jedna. Oferta nie uzupełnia dziury RCN. Inny obiekt, inna data, inna semantyka.
7. Heksagony licz osobno. RCN: mediana transakcji w heksagonie, próg n. Oferty: mediana lokali z inwestycji, której punkt wpadł w heksagon. Pusty heksagon zostaw pusty.

Nie scrapuj Otodom. AMRON nie jest publiczne. Portal DOM ma ruszyć około kwietnia 2027 i ma pokazywać mediany, nie rekordy.
