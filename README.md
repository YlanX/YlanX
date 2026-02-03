# Plenustech Backup Monitor (MVP)

Este repositório contém um MVP simples para priorizar problemas de backup a partir de logs enviados por e-mail do HQbird (Dataguard) e status do Acronis.

## Objetivo

- Identificar rapidamente casos críticos (banco corrompido, not found, ciclos, falta de espaço).
- Diferenciar eventos de verificação de backup e backups incrementais.
- Indicar se o Acronis está subindo backups corretamente.

## Como usar

1. Crie um arquivo de texto com o conteúdo do log.
2. Execute o analisador.

```bash
python monitor.py file --source hqbird --input caminho/para/log.txt
python monitor.py file --source acronis --input caminho/para/log.txt
python monitor.py file --source hqbird --input caminho/para/log.txt --keywords "corrompido,not found,lack of space"
```

## Conectar caixa de e-mail (IMAP)

Use variáveis de ambiente ou passe por flags:

```bash
export IMAP_HOST=imap.seuprovedor.com
export IMAP_USER=seu.usuario@empresa.com
export IMAP_PASS="sua-senha-ou-app-password"

python monitor.py imap --source hqbird --mailbox INBOX --limit 50 --keywords "corrompido,not found,lack of space"
```

## Próximos passos sugeridos

- Conectar uma caixa de e-mail para ingestão automática (IMAP/Graph API).
- Persistir eventos em banco (ex.: Postgres) e criar painéis.
- Configurar regras mais avançadas (ex.: identificar cliente, ambiente e SLA).
