# 🧽 Inventário de Limpeza

Quadro partilhado de casa para registar produtos de limpeza **em falta** ou
**repostos/comprados** — pensado para mim e para as empregadas de limpeza.

App web simples (Flask), em português, com separadores por zona:
**Cozinha · WCs · Roupa · Louça · Geral** + uma **Lista de Compras** (tudo o que
está em falta). Estado guardado no servidor e atualizado automaticamente entre
dispositivos. Corre no **porto 8002**.

## Como usar
- Toca em **Em falta** quando um produto acaba (fica vermelho e vai para Compras).
- Toca em **✓ Comprei** quando se repõe (volta a verde).
- **＋ Adicionar** cria um produto novo na zona ativa.
- Escreve o teu nome em **"Sou:"** para ficar registado quem marcou.

## Correr localmente
```bash
pip install -r requirements.txt
python app.py        # http://localhost:8002
```

## Docker (Raspberry Pi)
```bash
docker compose up -d --build
# http://<ip-do-pi>:8002
```
