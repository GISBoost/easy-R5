# 27,5% zasięgu Łodzi znika bez tramwaju

*Wersja robocza do bloga GISBoost + post na LinkedIn. Wszystkie liczby: patrz
`docs/notes/flagship-lodz-modal-results.md` i `out/*.csv`/`*.json` w tym folderze.*

## Wpis na bloga

**27,5% zasięgu Łodzi znika bez tramwaju.** Tyle z tego, co przeciętny mieszkaniec osiąga
w 30 minut transportem publicznym, jest dziś obsługiwane wyłącznie przez szyny — jeśli
tramwaj zniknie z sieci (autobus zostaje), tyle właśnie ubywa. Autobus odpowiada za nieco
mniej, 21,7%. A 13,6% zasięgu istnieje **tylko** dzięki temu, że można się między nimi
przesiąść — ani sam tramwaj, ani sam autobus by tego nie dały.

To ważne liczby akurat teraz: Łódź remontuje całą sieć tramwajową do 2029 roku — ze 124 km
torowisk zostało 20 km, w 2026 startuje pięć nowych placów budowy. Mapa "ile zasięgu zniknie
razem z tym korytarzem" nie jest ciekawostką akademicką, tylko czymś, co planista miejski
może użyć wprost.

**Jak to policzyliśmy.** Cztery przebiegi dostępności kumulatywnej na jednej sieci
(GTFS ZDiT, poniedziałek 2026-08-24, szczyt poranny 07:00–09:00, siatka 500 m) — pieszo,
tramwaj+pieszo, autobus+pieszo, cała sieć z przesiadkami — różniące się **wyłącznie** listą
trybów transitu, którymi może jechać silnik routingu [Conveyal R5](https://github.com/conveyal/r5).
Metoda to zawężona replika opublikowanej pracy
[Rayaprolu i Levinson (2024)](https://doi.org/10.1007/s11116-024-10555-9) o komplementarności
modalnej w Sydney — u nich sub-addytywność (tryby się częściowo dublują), u nas też: przy
30 minutach i dłużej `subadd < 1`. Ciekawe, że przy bardzo krótkich progach (15 min) wychodzi
odwrotnie — tryby się raczej uzupełniają, bo mało gdzie w ogóle się pokrywają.

Zanim ktoś zapyta: **to nie jest prognoza, tylko miara dzisiejszej zależności.** Model nie
uruchamia komunikacji zastępczej, nie przenosi pasażerów i nie przelicza rozkładu autobusów
po zamknięciu torowiska. Odpowiada na pytanie "ile z dzisiejszego zasięgu jedzie dziś na
szynach", a nie "co się stanie, jak zamkniemy tę konkretną linię".

Cała analiza — od budowy sieci R5 po policzenie czterech przebiegów — zajęła **niecałe
5,5 minuty routingu** na zwykłym laptopie, w [Easy-R5](https://github.com/GISBoost/easy-R5),
wtyczce QGIS do dostępności transportowej na silniku Conveyal R5. Kod, dane wejściowe i
dokładny przepis na odtworzenie wyniku: [tools/modal_complementarity_lodz](https://github.com/GISBoost/easy-R5/tree/main/tools/modal_complementarity_lodz).

---

## Post na LinkedIn

27,5% zasięgu Łodzi zniknęłoby bez tramwaju 🚋📉

Ile z tego, co mieszkaniec Łodzi osiąga w 30 minut transportem publicznym, zawdzięcza
konkretnie tramwajowi? Policzyłem to na silniku Conveyal R5, w mojej wtyczce do QGIS.

Metoda: cztery przebiegi dostępności na jednej sieci — pieszo, tramwaj, autobus, cała sieć
z przesiadkami — różniące się tylko listą trybów transitu. Reszta (siatka, cele, data,
godzina) identyczna.

Co wyszło:
🚋 27,5% zasięgu znika bez tramwaju, 21,7% bez autobusu
🔁 13,6% zasięgu istnieje tylko dzięki przesiadce tramwaj-autobus — ani jeden, ani drugi
   tryb osobno by tego nie dał
📊 przy progach 30 minut i dłuższych tramwaj i autobus częściowo się dublują
   (sub-addytywność), tak samo jak w opublikowanym badaniu dla Sydney
⏱️ cała analiza (budowa sieci + cztery przebiegi) zajęła niecałe 5,5 minuty na laptopie

Ważne zastrzeżenie: to jest miara dzisiejszej zależności, nie prognoza. Model nie uruchamia
komunikacji zastępczej i nie przenosi pasażerów — pokazuje, ile z dzisiejszego zasięgu jedzie
dziś na szynach, nie co się stanie po zamknięciu torowiska. Istotne przy trwającym remoncie
sieci tramwajowej w Łodzi (do 2029, ze 124 km torów zostało 20 km).

📥 Pełny opis metody i wyniki — link w komentarzu.

Easy-R5 jest open-source (GPL) — kod, dane i dokładny przepis na odtworzenie tego wyniku są
w repo. Chętnie usłyszę, co jeszcze warto by z tego policzyć.

#GIS #QGIS #OTP #transport #GISBoost #opensource
