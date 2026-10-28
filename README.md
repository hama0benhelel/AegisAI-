# AegisAI — Sécurisation d’un système multi-agents pour l’IoT

Démonstrateur académique indépendant réalisé dans le contexte d’un stage
cybersécurité chez Be Wireless Solutions. Clients, capteurs et consommations
sont synthétiques ; aucune connexion aux systèmes ou équipements de BWS.

Un client consulte ses consommations d’eau, d’électricité et de gaz dans une
interface unique. Le chatbot consulte les données autorisées, explique les
analyses et prépare des opérations que le client valide explicitement.
Trois services agents distincts communiquent avec le backend par mTLS.

## Comptes et responsabilités

| Compte de démonstration | Rôle | Accès |
|---|---|---|
| client.a@example.test | client | Données et opérations de A |
| client.b@example.test | client | Données et opérations de B |
| security.admin@bws.example.test | security_admin | Métadonnées de sécurité inter-tenants, sans données de consommation |
| soc_admin | Administrateur Grafana | Supervision SOC ; compte distinct de l’application |

Les mots de passe restent locaux. Les anciens rôles viewer, operator et
tenant_admin sont conservés pour compatibilité et certains tests. Ils ne sont
pas les comptes du parcours client final. `admin.a` sert notamment à vérifier
l’isolation des conversations entre deux utilisateurs d’un même tenant.

## Fonctions livrées

- JWT HS256, mots de passe Argon2id, utilisateur actif et rôle relus en base.
- Autorisations API, PostgreSQL RLS forcée et rôles DB spécialisés.
- Agents eau, énergie et gaz isolés en conteneurs, sans accès DB ni clé Groq.
- Vérification mTLS, nom du serveur et validation des réponses agents.
- Simulateur horaire avec six compteurs, insertions idempotentes et droits limités.
- Chat conversationnel avec contexte serveur privé et clarification des ambiguïtés.
- Lecture dernière mesure, aujourd’hui ou hier ; sommes journalières déterministes.
- Conseils généraux sourcés issus d’un catalogue local dont l’empreinte est vérifiée.
- Analyse prévisualisée puis enregistrée après confirmation personnelle.
- Proposition approuvée ou refusée, puis création explicite d’une tâche unique.
- Journal des appels Groq, quotas locaux, validation des sorties et réponses de secours.
- Audit, collecte Alloy/Loki, dashboards et alertes Grafana.
- SSH par clé, fail2ban et rotation des logs Docker pour la VM de démonstration.

## Architecture et stack

React/Vite → Nginx → FastAPI → PostgreSQL.
Le backend appelle les agents eau/énergie/gaz par HTTPS avec certificat client.
Groq (`openai/gpt-oss-20b`) sert au routage sémantique et à certaines reformulations.
Alloy collecte les logs ; Loki les stocke ; Grafana évalue les alertes.

Le LLM ne possède ni connexion PostgreSQL ni outil d’exécution. Le message brut
peut être envoyé au routeur sémantique quand les règles locales ne suffisent pas.
La génération de réponse reçoit un contexte structuré déjà autorisé.

## Redémarrer la VM déjà préparée

Ces commandes supposent les migrations 001 à 016 appliquées, les secrets locaux,
comptes, données et certificats déjà configurés. Ce n’est pas un installateur vierge.
Les chemins PKI de Compose correspondent à `/home/bws/.local/share/aegisai-pki`.

```bash
cd ~/aegisai
sudo -v
bash scripts/aegis.sh config --quiet
bash scripts/aegis.sh up -d
python3 scripts/update_log_targets.py
bash scripts/aegis.sh restart alloy
bash scripts/aegis.sh ps
curl --max-time 10 -fsS http://127.0.0.1:8080/api/health/ready
curl --max-time 5 -fsS http://127.0.0.1:3000/api/health
curl --max-time 5 -fsS http://127.0.0.1:3100/ready
```

Le wrapper utilise les quatre fichiers Compose et fonctionne depuis n’importe
quel répertoire. Après recréation d’un backend, frontend ou agent, régénérer les
cibles Alloy et redémarrer Alloy. Loki peut retourner 503 pendant son démarrage.
L’état Running d’un agent ne remplace pas une probe mTLS.

Depuis le Mac, dans une fenêtre dédiée :

```bash
ssh -i ~/.ssh/aegisai_vm -o IdentitiesOnly=yes -N \
  -L 8080:127.0.0.1:8080 -L 3000:127.0.0.1:3000 bws@192.168.64.19
```

Application : http://localhost:8080 ; Grafana : http://localhost:3000.
Adapter l’adresse si la VM change d’IP. Les ports applicatifs sont publiés sur
localhost ; PostgreSQL et les agents n’ont pas de port publié sur l’hôte.

## Validation

```bash
# Tests avec réseau/DB simulés ; pas d’appel Groq réel.
bash scripts/check_local_controls.sh

# Contrôles SQL en transaction read-only sur la base de démonstration.
bash scripts/aegis.sh exec -T db \
  psql -X -U postgres -d aegisai -v ON_ERROR_STOP=1 \
  < tests/check_database_security.sql
```

Scénarios API, prérequis et preuves : [docs/security/validation_matrix.md](docs/security/validation_matrix.md).
Les tests `check_*.py` ne sont pas tous des tests isolés : certains créent des
analyses/tâches, demandent des comptes historiques ou nécessitent un quota Groq.
Ne pas les lancer tous par découverte automatique.
Les tests d’alertes envoient des instructions hostiles contrôlées ou arrêtent
provisoirement gas-agent : les exécuter séparément dans le lab.

## Secrets et limites

Ne pas publier `.env`, clés privées, certificats privés ou dumps. Le fichier
`.env.example` décrit uniquement les variables, sans secret réel.

Les agents appliquent une règle déterministe non calibrée : ce ne sont pas des
modèles ML entraînés. Aucun diagnostic de fuite, cause racine, pourcentage de
fiabilité, ROI ou commande physique n’est garanti. Une tâche créée est une ligne
DB, pas une inspection réalisée. Le client peut être auteur et approbateur.
Les regex et tests d’injection ne prouvent pas une protection universelle.
La validation des références LLM ne garantit pas toute assertion générée.
Le free tier Groq peut être limité ou indisponible.

Pas de validation complète d’installation sur VM vierge, de TLS 1.3 bout en bout,
de chiffrement AES-256/LUKS démontré ou de certification GDPR/IEC 62443.

## Documentation

- [Architecture](docs/architecture.md)
- [Contrôles et limites de sécurité](docs/security_layer.md)
- [Exploitation et livraison](docs/operations.md)
- [Validation sécurité](docs/security/validation_matrix.md)
- [Runbook des alertes](docs/security/monitoring_alert_runbook.md)
- [Menaces sur les conseils](docs/security/recommendation_threat_model.md)
- [Évaluations et rapports](docs/evaluation/)
