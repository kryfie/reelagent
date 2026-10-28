# ReelAgent 2.4 — trzy propozycje, jeden eksport

Działająca aktualizacja ReelAgent 2.3 dla obecnego repozytorium GitHub i jednej usługi Render. Własne materiały fotograficzne i krótkie nagrania -> trzy podglądy -> wybór -> MP4.

## Co nowego

- **Filmowy, Dynamiczny, Historia:** trzy osobne plany montażu na podstawie tych samych materiałów, utworzone jednocześnie.
- **Podgląd w przeglądarce** bez renderowania trzech MP4; lokalne zdjęcia, oryginalne wideo, kolejność/tempo scen, napisy i przybliżenia. Nie jest to jeszcze gotowy plik.
- **Przesuwanie palcem w poziomie** na podglądzie + strzałki, kropki i trzy widoczne przyciski. Jest też Play/Pause i przewijanie.
- **Tylko wybrany wariant** jest wysyłany na Render i eksportowany jako MP4 540 × 960 po kliknięciu „Wybieram ten wariant — wygeneruj MP4”.
- Ożywione napisy (płynne wejście), kilka delikatnych akcentów graficznych zależnych od stylu, bez wielkich szarych tablic; zachowana bezpieczna strefa.
- Zachowane opcjonalne Florence-2, nagrywanie pięciosekundowe, zmiana tekstów scen, logo i muzyka, pamięć marki oraz `APP_PIN`.

**Ważne:** podgląd jest szybkim przybliżeniem końcowego montażu. Efektów FFmpeg (dokładny zoom, fonty, klatki źródłowe, intro napisów, plansza końcowa) nie da się idealnie odwzorować w DOM; końcowy MP4 może się nieco różnić. Podgląd nie odtwarza wgranej ścieżki dźwiękowej; końcowy eksport ją dodaje.

## Aktualizacja (bez nowej usługi Render)

1. Pobierz ZIP i rozpakuj.
2. Skopiuj **zawartość** folderu do obecnego lokalnego repozytorium ReelAgent, nadpisując pliki. Dodaj nowy `static/variants.js` i zaktualizowany `app.py`.
3. W GitHub Desktop zrób **Commit** i **Push**.
4. Przy włączonym Auto-Deploy Render wdroży nową wersję. Używaj dotychczasowego adresu i `APP_PIN` z Render → Environment.
5. Odśwież stronę telefonu (w razie potrzeby zamknij starą kartę i otwórz ponownie).

Nie potrzeba nowych zmiennych środowiskowych ani dodatkowych usług API. Nadal obowiązuje opłata za Twój istniejący plan Render (~7 USD miesięcznie), a przy dużym ruchu mogą pojawić się ograniczenia zasobów / dodatkowe koszty.

## Wymagania i ograniczenia

- 2–8 materiałów; zdjęcie do **8 MB**, wideo do **15 MB** i **8 sekund**, całość do **60 MB**. Własne nagrywanie: **5 sekund**.
- Limity sprawdzane na froncie i ponownie na serwerze. Nie wgrywaj długich nagrań do publicznej aplikacji. Dla eksportu wymagany jest kod, jeśli ustawiono `APP_PIN`.
- Wszystkie zdjęcia i nagrania służą do eksportu jednego wariantu. **Nie dodawaj materiałów klientów do publicznego repozytorium.**
- Pliki są przechowywane tymczasowo, a wynik dostępny do ~1 godziny. Restart usługi Render może przerwać trwające zadania.
- Trzy podglądy wykorzystują zasoby *urządzenia użytkownika*, a nie trzy oddzielne rendery na serwerze. Na starszym telefonie przełączanie filmów może być mniej płynne.
- Generowanie nowych realistycznych scen image-to-video nie jest częścią tej wersji. Opcjonalna analiza Florence-2 nadal zależy od zgodności urządzenia.

## Weryfikacja

W środowisku z Pythonem, zależnościami i FFmpeg:

```bash
pip install -r requirements.txt
python tests/test_three_variants.py
python tests/test_director.py
python tests/test_limits.py
```

`tests/test_three_variants.py` potwierdza: trzy różne plany, poprawne czasy i indeksy, odrzucenie błędnych planów, **jeden** wybrany render oraz powstanie pliku MP4 o właściwej długości. Wykonano też test interfejsu 390×844: wybór kart, strzałki, kropki, podgląd i pasek postępu.

## Struktura

- `app.py` — API planów, limity przesyłania, renderowanie FFmpeg i pobieranie MP4
- `director.py` — deterministyczny reżyser scen
- `static/app.js` — formularz, pliki, nagrywanie, eksport
- `static/variants.js` — trzy lekkie odtwarzane w przeglądarce propozycje i wybór
- `static/index.html`, `static/style.css` — interfejs
- `static/director-ai.js` — opcjonalna analiza Florence-2

## Bezpieczeństwo

Nie umieszczaj `APP_PIN` w publicznym GitHubie. Render → Environment → `APP_PIN` to prawidłowe miejsce. Repozytorium może być publiczne, ale zdjęcia użytkowników i pliki wideo nie mogą trafiać do commita ani publicznych artefaktów.
