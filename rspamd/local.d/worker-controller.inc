# Rspamd worker-controller – HTTP API na porcie 11333
# Wyłączamy hasło bo Rspamd jest w sieci wewnętrznej Docker (nie wystawiony na zewnątrz)
# W produkcji z zewnętrznym dostępem DODAJ: password = "hasło"
bind_socket = "*:11333";
