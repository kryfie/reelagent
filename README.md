# ReelAgent 2.0 — zdjęcia / krótkie filmy → rolka MP4

Nowa wersja poprzedniego ReelAgent Starter. Strona na telefon i komputer: wgrywasz od 2 do 8 zdjęć **lub filmów**, edytujesz **dwa napisy dla każdej sceny**, zmieniasz kolejność strzałkami, wybierasz jeden z trzech stylów i długość **10 / 15 / 20 sekund**, po czym otrzymujesz pionowy MP4 540×960, 20 fps (H.264) do obejrzenia, pobrania i udostępnienia.

## Najważniejsza nowość: napisy poza ikonami TikToka i Instagrama

Wszystkie generowane przez ReelAgent napisy — główne, dodatkowe, nazwa marki i końcowe CTA — są rysowane **wyłącznie w zachowawczej strefie centralnej**. Przy rozdzielczości 540×960 to prostokąt od **x = 38 do 404 px, y = 150 do 670 px**. Nie dodajemy tekstu w obszarze przycisków po prawej stronie (x >= 414 px), przy opisie na dole (y >= 690 px) ani w górnym pasku (y < 145 px). Przycisk „Pokaż strefę TikToka i Instagrama” w podglądzie pokazuje orientacyjne marginesy — ten przewodnik **nie jest renderowany w MP4**.

Uwaga: interfejs obu platform, format publikacji i nakładki reklamowe zmieniają się. Nie ma jednego oficjalnego prostokąta gwarantującego całkowitą widoczność na każdym urządzeniu; sprawdź także podgląd w TikToku / Instagramie przed publikacją. Tekst obecny **na zdjęciu wgranym przez użytkownika** nie jest przenoszony ani usuwany. Bezpieczna strefa obejmuje tylko tekst dodawany przez aplikację.

## Trzy style montażu

- **Filmowy:** przybliżenia, spokojne ruchy, ciepłe kolory, prosty panel typograficzny.
- **Dynamiczny:** bardziej energiczny ruch kadru, większy kontrast i mocny napis.
- **Historia:** kolejne ujęcia jako sceny opowieści, numery scen, spokojniejsza oprawa.

Wideo MP4/MOV/WEBM jest używane jako rzeczywiste **ruchome ujęcie**; ścieżka dźwiękowa oryginalnych nagrań jest wyciszana, aby uniknąć przypadkowego miksu. Można dodać jeden własny podkład muzyczny MP3/M4A/WAV, do którego posiadasz prawa. Krótkie wideo jest zapętlane na czas sceny. Zdjęcia są delikatnie panoramowane i przybliżane w FFmpeg. **Nie jest to generowanie nowych ruchomych scen przez model AI** — do tego potrzeba osobnej integracji i zasobów.

## Aktualizacja istniejącej usługi Render (Starter 7 USD)

**Nie zakładaj kolejnej płatnej usługi Render.** Skorzystaj z już istniejącego repozytorium i Web Service ReelAgent:

1. Rozpakuj `reelagent-v2.zip` na komputerze.
2. Skopiuj **pliki znajdujące się wewnątrz folderu projektu** do katalogu **obecnego** repozytorium ReelAgent i zastąp pliki wersji 1.0. `Dockerfile` i `app.py` mają leżeć w głównym katalogu repozytorium, katalog `static/` obok nich.
3. Zrób commit i push przez GitHub Desktop.
4. Render automatycznie zbuduje nową wersję, jeśli masz połączony GitHub i Auto-Deploy; w innym razie kliknij **Manual Deploy → Deploy latest commit**.
5. Otwórz **swój dotychczasowy adres** `*.onrender.com`. W razie wyświetlania starego UI odśwież stronę.
6. **Nie zmieniaj `APP_PIN`** ustawionego w Render → Environment. Wersja 2.0 używa tego samego pola kodu dostępu.
7. Dodaj 3 zdjęcia lub 2 zdjęcia i 1 krótkie nagranie, popraw teksty przy scenach, wybierz szablon, kliknij **Wygeneruj rolkę**. Podgląd MP4 i pobranie/udostępnienie pojawią się po renderowaniu.

Do istniejącej usługi nie potrzeba dodawania zmiennych środowiskowych ani tworzenia Blueprinta. Plik `render.yaml` jest pomocniczy i **nie należy uruchamiać z niego nowej instancji**, jeśli nie chcesz opłacać drugiej usługi.

### Zapis w Zdjęciach iPhone'a

Na obsługiwanych iPhone'ach przycisk „Udostępnij / Zapisz w Zdjęciach” uruchamia systemowy arkusz udostępniania z plikiem MP4. Wybierz „Zachowaj wideo”, o ile Safari udostępnia tę opcję. Alternatywnie wybierz „Pobierz MP4”, potem aplikację Pliki → Udostępnij → Zachowaj wideo. Udostępnianie wymaga HTTPS (Render dostarcza HTTPS). Funkcji **nie testowano na fizycznym iPhonie**.

## Limity wersji testowej

- 2–8 zdjęć/krótkich filmów; do 8 materiałów łącznie.
- Pojedynczy obraz max 12 MB; pojedynczy film max 55 MB; cały upload max 145 MB; opcjonalna muzyka max 15 MB.
- Długość przesłanego filmu do 90 sekund, ale do rolki trafia tylko fragment o długości przypadającej na scenę.
- Render Starter (0,5 CPU / 512 MB RAM) może działać powoli przy kilku filmach wejściowych i dużych plikach. To **prototyp, nie gotowy publiczny SaaS**.
- Jeden render jednocześnie; maksymalnie dwa zadania oczekujące/aktywne; materiał w katalogu tymczasowym; gotowy MP4 dostępny przez ok. godzinę od utworzenia zadania. Pobierz od razu.
- Kod można trzymać na publicznym GitHubie; **nie zapisuj tam prywatnych zdjęć, filmów, muzyki, kodów APP_PIN ani danych klientów.** Pliki użytkowników trafiają tymczasowo wyłącznie na serwer Render. Jeśli włączasz usługę publicznie, potrzebujesz pełniejszego zabezpieczenia dostępu i kontroli treści.
- Nie jest wykorzystywane płatne API AI. Nie ma więc kosztu „za generację AI”, ale jest opłata za Twój plan Render i ewentualne dalsze koszty transferu/zasobów.

## Lokalny test

Wymagania: Python 3.11+, systemowy `ffmpeg` i `ffprobe` oraz czcionki DejaVu.

```sh
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

Test automatyczny (sprawdza zdjęcia, wideo i faktyczny plik H.264 MP4):

```sh
python tests/test_smoke.py
```

## Układ projektu

- `app.py`: FastAPI, walidacja, sceny, bezpieczny obszar tekstu, FFmpeg.
- `static/index.html`, `static/style.css`, `static/app.js`: interfejs mobilny, napisy scen, wybór szablonu, podgląd, pobranie.
- `Dockerfile`: instalacja FFmpeg, Pillow i zależności.
- `render.yaml`: pomocnicza konfiguracja (nie używaj do tworzenia drugiej usługi).
- `tests/test_smoke.py`: test renderowania dwóch wariantów.
