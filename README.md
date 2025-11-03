# narzedzia.lh.pl

Narzędzie do testowania maila, SSL i DNS z konsoli, wszystko przez curl.

- **mail tester** - wysyłasz maila na wygenerowany adres i dostajesz ocenę (spam score, SPF/DKIM, PTR, RBL)
- **SSL** - sprawdza certyfikat domeny
- **DNS** - sprawdza propagację rekordów na kilku serwerach DNS

Backend to FastAPI + Redis, maile przyjmuje Postfix, a ocenia je Rspamd. Wszystko w dockerze.

## Uruchomienie

```bash
cp .env.example .env    # ustaw swoją domenę
make build
make up
```

API jest na `http://localhost:8000`, sprawdzenie czy działa: `curl localhost:8000/health`

## Przykłady

```bash
curl -X POST localhost:8000/api/v1/jobs/ -H 'Content-Type: application/json' -d '{"label":"test"}'
curl localhost:8000/api/v1/jobs/{job_id}
curl localhost:8000/api/v1/ssl/github.com
curl localhost:8000/api/v1/dns/github.com/MX
```

## Testy

```bash
make test       # potrzebny redis na :6379
make test-all   # razem z testami które idą do internetu
```

## DNS pod mail tester

```
testmail.b-1.pl.        MX  10 mx.testmail.b-1.pl.
mx.testmail.b-1.pl.     A      <IP_VPS>
testmail.b-1.pl.        TXT    "v=spf1 ip4:<IP_VPS> ~all"
```

Do tego PTR na IP serwera ustawiony u dostawcy VPS.
