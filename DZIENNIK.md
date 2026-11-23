# Dziennik zdarzeń

Wszystko, co pomoże kiedyś zrozumieć dane: przerwy w zbieraniu, awarie czujników, zmiany w kodzie, sztormy, ulewy, roztopy, lód, prace na rzece. Wpisuj krótko, najnowsze na górze. Czas lokalny, chyba że zaznaczono inaczej.

Rodzaje wpisów: **ZBIERACZ** (kod, przerwy), **CZUJNIK** (podejrzane wartości, awarie), **ZJAWISKO** (pogoda, woda, lód), **INNE** (prace, budowy, zmiany w źródłach).

Szablon:

```
### RRRR-MM-DD GG:MM – RODZAJ – krótki tytuł
Co się stało. Których stacji dotyczy. Skąd wiadomo (obserwacja, zdjęcie, komunikat, wiadomości).
```

---

### 2026-11-23 20:58 – ZBIERACZ – zmiana trybu zbierania
Harmonogram „co 15 minut” w GitHub Actions działał w praktyce co 60–90 minut, więc większość pomiarów przepadała. Od tej chwili przebieg uruchamia się co godzinę i sam pobiera dane 6 razy co ok. 14 minut. Usunięto zdublowany plik workflow i stary plik `archiwum/hydrowskaz/2026-11-22.jsonl`.

### 2026-11-23 ok. 0:45 – ZBIERACZ – start archiwum
Pierwszy zapis do `archiwum/`. Najwcześniejsze pomiary: IMGW z 22.11.2026, 23:40 UTC, Hydrowskaz z 23.11.2026, 0:30 UTC. Jedynym wcześniejszym wpisem jest dobowa suma opadu IMGW do 6:00 UTC 22.11.
