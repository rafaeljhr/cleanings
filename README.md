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

## 🆘 Deploy do zero (se o Raspberry Pi morrer)

Num Raspberry Pi novo com **Raspberry Pi OS (64-bit)** e SSH ligado:

1. Atualizar o sistema e instalar o Docker:
   ```bash
   sudo apt update && sudo apt upgrade -y
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER && newgrp docker   # usar o docker sem sudo
   ```
2. Clonar este repositório e arrancar:
   ```bash
   git clone https://github.com/rafaeljhr/cleanings.git
   cd cleanings
   docker compose up -d --build
   ```
3. Aceder em **http://<ip-do-pi>:8002** (descobre o IP com `hostname -I`).

O serviço tem `restart: unless-stopped` e o Docker arranca no boot, por isso volta
a subir sozinho após reinícios ou falhas de energia.

### Backup / reposição dos dados
O inventário de limpeza fica num volume Docker chamado `cleanings_data`.

```bash
# backup -> cria backup.tar.gz na pasta atual
docker run --rm -v cleanings_data:/data -v "$PWD":/backup alpine tar czf /backup/backup.tar.gz -C /data .

# repor a partir de backup.tar.gz
docker run --rm -v cleanings_data:/data -v "$PWD":/backup alpine tar xzf /backup/backup.tar.gz -C /data
```

### Atualizar para a versão mais recente
```bash
cd cleanings && git pull && docker compose up -d --build
```
