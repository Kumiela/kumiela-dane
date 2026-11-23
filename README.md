# kumiela-dane

Archiwum pomiarów hydrologicznych i meteorologicznych z Elbląga i okolic: rzeka Kumiela (Hommel), rzeka Elbląg, jezioro Drużno i Zalew Wiślany. Dane zbiera automatycznie skrypt `zbieraj.py` uruchamiany w GitHub Actions. Archiwum powstaje przy stronie krajoznawczej o Kumieli i ma posłużyć później do analiz.

Początek zbierania: **23 listopada 2026, ok. 0:40 czasu lokalnego** (22.11.2026, 23:40 UTC).

## Źródła

| Źródło | Co | Stacje |
|---|---|---|
| [Hydrowskaz Miasta Elbląg](https://elblag.hydrowskaz.pl/) | stany wody, opad, wiatr, temperatura czujnika | 11 stacji ATSHM01–ATSHM11 |
| [IMGW-PIB](https://hydro.imgw.pl/), dane publiczne | stany wody | Elbląg, Żukowo (Drużno), Nowe Batorowo i Tolkmicko (Zalew) |
| IMGW-PIB, dane publiczne | opad, temperatura, wiatr, wilgotność | stacja meteorologiczna Elbląg (254190190) |

Pełna lista stacji ze współrzędnymi i mierzonymi wielkościami jest w [`stacje.csv`](stacje.csv).

Źródło danych IMGW: Instytut Meteorologii i Gospodarki Wodnej – Państwowy Instytut Badawczy. Dane IMGW-PIB zostały przetworzone. Dane Hydrowskazu należą do Miasta Elbląg. Przed publicznym udostępnieniem przetworzonego zbioru trzeba ustalić warunki z właścicielem.

## Jak zbierane są dane

- GitHub Actions uruchamia zbieracza co godzinę. Jeden przebieg trwa ok. 70 minut i pobiera dane 6 razy, co ok. 14 minut. Do 23.11.2026 harmonogram był ustawiony „co 15 minut”, ale GitHub uruchamiał go w praktyce co 60–90 minut. Dlatego w danych z 22–23.11.2026 są przerwy.
- Każdy przebieg zapisuje tylko **nowe** pomiary. Pomiar o tym samym czasie, stacji i wielkości nie jest zapisywany drugi raz.
- Zbieracz zapisuje to, co źródło pokazuje w chwili odczytu, czyli zwykle ostatni pomiar. Jeśli zbieracz nie działał, pomiary z tego okresu przepadają, bo źródła nie udostępniają historii.
- Czasy są w **UTC**. Hydrowskaz podaje czas lokalny (Europe/Warsaw), który skrypt przelicza na UTC. IMGW podaje UTC.

## Pliki

### `archiwum/hydrowskaz/RRRR-MM.csv`

Jeden wiersz to jeden pomiar jednego czujnika.

| kolumna | opis |
|---|---|
| `czas_utc` | czas pomiaru, UTC, `RRRR-MM-DDTGG:MMZ` |
| `stacja_id` | numer stacji w Hydrowskazie (patrz `stacje.csv`) |
| `stacja` | nazwa stacji |
| `czujnik` | nazwa czujnika, tak jak podaje Hydrowskaz |
| `wartosc` | wartość |
| `jednostka` | jednostka |

Uwagi:
- „Poziom wody” w metrach to stan względem zera danego czujnika, a nie wysokość n.p.m. Wartości z różnych stacji nie są ze sobą bezpośrednio porównywalne. Wysokość n.p.m. podają osobne czujniki „Poziom wody w m n.p.m” na stacjach 127 i 338.
- „Suma opadu” to licznik narastający, który może być zerowany. Opad za dany okres liczy się z różnicy odczytów. Skrypt robi to w `dane/opad_hydrowskaz.json`.
- Nazwy czujników mają niejednolitą pisownię, np. „Intensywnosc opadu” i „Intensywność opadu”. Są zapisane dokładnie tak, jak podaje źródło.

### `archiwum/imgw/RRRR-MM.csv`

| kolumna | opis |
|---|---|
| `czas_utc` | czas pomiaru, UTC |
| `zrodlo` | zawsze `imgw` |
| `stacja` | kod stacji IMGW |
| `wielkosc` | `stan_wody`, `opad_10min`, `opad_1h` … `opad_24h`, `opad_doba_do_6utc`, `temp_powietrza`, `temp_gruntu`, `wiatr_sredni`, `wiatr_max`, `wiatr_kierunek`, `wilgotnosc` |
| `wartosc` | wartość |
| `jednostka` | `cm`, `mm`, `C`, `m/s`, `deg`, `%` |

### `dane/`

Ostatni odczyt, z którego korzysta strona o Kumieli. Pliki są nadpisywane przy każdym przebiegu i nie stanowią archiwum.

- `hydrowskaz.json`: surowy ostatni odczyt Hydrowskazu
- `imgw.json`: ostatni odczyt IMGW wraz ze stanami ostrzegawczymi i alarmowymi
- `opad_hydrowskaz.json`: opad 1/3/6/24 h przy Goplanicy (127) i Drużnie (138)
- `log.json`: wynik ostatniego przebiegu, czyli co się udało, a co nie

### `DZIENNIK.md`

Ręczny dziennik zdarzeń: awarie, przerwy, zmiany w zbieraczu, nietypowe sytuacje pogodowe i hydrologiczne. Potrzebny do interpretacji danych.

## Ograniczenia

- Hydrowskaz mierzy **stany** wody, a nie przepływy.
- Nie są znane sposób kalibracji czujników ani rzędne ich zer.
- Pomiary nie są weryfikowane. To surowe dane operacyjne, które mogą zawierać błędy czujników.
