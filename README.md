# ReelAgent Starter 1.0 — zdjęcia → rolka MP4

Działająca strona mobilna: dodajesz **2–8 zdjęć**, wybierasz styl, dopisujesz tekst, opcjonalnie własną muzykę i logo. Aplikacja generuje pionowe MP4, umożliwia podgląd, pobranie i udostępnienie do aplikacji Zdjęcia (jeżeli system na to pozwala).

**To jest wersja 1.0 z automatycznym montażem, a nie generatywne AI.** Animuje prawdziwe zdjęcia, nie wymyśla nowych ruchomych scen. Nie wykorzystuje klucza AI, nie generuje rachunków za API. Kolejne wersje mogą dostać analizę zdjęć przez AI i pamięć stylu marki.

## Jak opublikować na GitHub + Render (Free)

1. Utwórz **osobne repozytorium** GitHub, np. `reelagent-starter`. Nie dodawaj tam zdjęć klientów, muzyki ani kluczy.
2. Rozpakuj ZIP i skopiuj **zawartość folderu `reelagent-starter`** do katalogu repozytorium (Dockerfile musi być w głównym katalogu). Wykonaj commit/push, np. przez GitHub Desktop.
3. Otwórz https://dashboard.render.com/ → **New → Web Service**, połącz repozytorium.
4. Jako **Language/Runtime wybierz Docker** (plik `Dockerfile` instaluje FFmpeg). Jako plan wybierz **Free**.
5. Opcjonalnie w **Environment** ustaw `APP_PIN` na własny kod, aby tylko osoby znające kod mogły generować rolki. **Nie wpisuj kodu w repozytorium**. Pole do wpisania kodu jest już na stronie.
6. Po wdrożeniu Render pokaże adres `https://twoja-nazwa.onrender.com`. Wejdź na niego na telefonie.
7. Wgraj 3–4 zdjęcia, kliknij **Wygeneruj rolkę**, obejrzyj wynik, kliknij **Udostępnij / Zapisz w Zdjęciach**.

Na iPhonie w natywnym oknie udostępniania może się pojawić **Zachowaj wideo**. Jeżeli nie, wybierz **Pobierz film MP4** i otwórz plik w aplikacji **Pliki**, a następnie udostępnij/zachowaj. Zachowanie zależy od wersji iOS i przeglądarki.

### Ograniczenia Render Free

- Serwer usypia się po 15 minutach bezczynności, pierwsze wejście może trwać około minuty.
- Render Free ma skromny procesor; film może generować się wolniej niż na komputerze. Rozdzielczość w MVP to **540×960, 20 fps**, żeby ograniczyć koszty obliczeń.
- Pliki są **tymczasowe** i znikają po upływie godziny od utworzenia zadania (przy kolejnym żądaniu), a także po restarcie lub uśpieniu Rendera. Pobierz gotowy plik od razu.
- Maksymalnie 2 zlecenia w kolejce, 1 render jednocześnie. Prototyp do prywatnych testów, nie do udostępniania publicznego klientom jako usługa komercyjna.
- Kod może być publiczny, ale zdjęcia nie trafiają do repozytorium GitHub. Są przesyłane do serwera Render i chwilowo zapisane w katalogu tymczasowym; nie przesyłaj prywatnych materiałów.
- Aby uruchamiać komercyjny SaaS, będzie potrzebny skalowalny backend, kontrola płatności, limity i polityka danych.

## Test lokalny (Windows / macOS / Linux)

Wymagane Python 3.11+ i zainstalowany FFmpeg dostępny w `PATH`.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

Otwórz `http://127.0.0.1:8000` na komputerze. Na prawdziwym iPhonie testuj HTTPS na Renderze (Web Share API wymaga bezpiecznego kontekstu).

## Struktura plików

- `app.py` — backend FastAPI, przygotowanie grafik i montaż FFmpeg.
- `static/index.html`, `style.css`, `app.js` — mobilny interfejs, podgląd i zapis.
- `Dockerfile` — instalacja FFmpeg i start na Renderze.
- `render.yaml` — opcjonalny przepis do Render Blueprint.

## Bezpieczeństwo i materiały

Darmowe repozytorium GitHub jest publiczne tylko dla **kodu**. Nie umieszczaj w nim zdjęć lub filmów klientów. W pilotażu ustaw `APP_PIN`, nie udostępniaj szeroko adresu strony. Zdjęcia przesyłaj tylko za zgodą właściciela. Korzystaj z muzyki, do której masz prawo w kontekście publikacji firmy.
