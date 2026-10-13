# AegisAI — Secure AI Agent Platform for IoT

Prototype académique de sécurité et de gouvernance pour une plateforme
d’agents IA appliquée aux consommations IoT, réalisé dans le contexte
d’un stage en cybersécurité chez Be Wireless Solutions.

Le démonstrateur est indépendant des systèmes de l’entreprise.
Les organisations, capteurs et mesures sont synthétiques.

## Fonctionnalités

- Deux organisations isolées : Client A et Client B.
- Authentification JWT et mots de passe Argon2id.
- Rôles viewer, operator et tenant_admin.
- Isolation API et PostgreSQL Row-Level Security.
- Analyses eau et énergie par règle déterministe.
- Assistant à intentions contrôlées utilisant Groq.
- Confirmation avant enregistrement d’une analyse via le chatbot.
- Approbation avant création d’une tâche d’inspection.
- Audit et journal des appels LLM.
- Supervision Alloy, Loki et Grafana avec alertes.
- SSH par clé, fail2ban et rotation des logs Docker.

## Stack

| Composant | Technologie |
|---|---|
| Backend | FastAPI, Uvicorn, Python |
| Base de données | PostgreSQL 17 |
| Interface | React, Vite, Nginx |
| LLM distant | Groq — openai/gpt-oss-20b |
| Supervision | Grafana Alloy, Loki, Grafana |
| Déploiement | Docker Compose, Ubuntu ARM64 |

Les agents utilisent des règles de calcul, pas des modèles ML entraînés.
Groq reformule des données autorisées préparées par le backend.
Il ne dispose pas d’accès direct à PostgreSQL ni d’outils d’exécution.

## Comptes de démonstration

| Compte | Organisation | Rôle |
|---|---|---|
| viewer.a@example.test | A | viewer |
| operator.a@example.test | A | operator |
| admin.a@example.test | A | tenant_admin |
| admin.b@example.test | B | tenant_admin |

Les mots de passe sont configurés localement.
Un tenant_admin administre uniquement son organisation.
Grafana utilise un compte SOC distinct : soc_admin.

## Démarrage de la VM déjà préparée

Ces commandes supposent que les secrets, migrations et données
de démonstration sont déjà configurés.

    cd ~/aegisai
    sudo docker compose -f compose.yaml -f compose.monitoring.yaml up -d
    python3 scripts/update_log_targets.py
    sudo docker compose -f compose.yaml -f compose.monitoring.yaml restart alloy

Les chemins des logs doivent être actualisés après recréation
des containers backend ou frontend.

Vérification :

    curl -fsS http://127.0.0.1:8080/api/health/ready
    curl -fsS http://127.0.0.1:3000/api/health
    curl -fsS http://127.0.0.1:3100/ready

Loki peut retourner temporairement 503 pendant son démarrage.

## Accès depuis le Mac

    ssh -i ~/.ssh/aegisai_vm -o IdentitiesOnly=yes -N -L 8080:127.0.0.1:8080 -L 3000:127.0.0.1:3000 bws@192.168.64.19

L’adresse de la VM peut évoluer.

- Application : http://localhost:8080
- Grafana : http://localhost:3000

Les ports applicatifs sont publiés sur localhost dans la VM.
PostgreSQL ne possède pas de port publié sur l’hôte.

## Secrets

.env reste local avec permissions restrictives.
Ne pas versionner les clés API, secrets JWT, mots de passe,
clés SSH privées ou sauvegardes contenant des données sensibles.

## Tests principaux

Depuis Ubuntu :

    python3 tests/check_chat_confirmation.py
    python3 tests/check_llm_boundaries.py
    python3 tests/check_llm_journal.py

Tests isolés sans appel Groq :

    sudo docker compose exec -T backend python - < tests/test_llm_controls.py

check_chat.py attend LLM_ENABLED=false.
check_llm_boundaries.py nécessite un LLM actif et une quota disponible.

D’autres tests couvrent JWT, RBAC, isolation, agents et workflow.
Les résultats d’évaluation sont conservés dans docs/evaluation/.

## Limites

- Trois intentions actives sur les six de la taxonomie.
- Pas de cause racine confirmée ni de score de confiance calibré.
- Références valides et JSON correct ne garantissent pas toute assertion.
- Pas de commandes envoyées aux équipements.
- Une tâche enregistrée ne signifie pas inspection réalisée.
- Pas de séparation obligatoire entre auteur et approbateur.
- Installation sur une VM vierge non validée de bout en bout.
- Pas de déclaration de conformité GDPR ou IEC 62443.

## Documentation

- docs/architecture.md : composants et flux.
- docs/security_layer.md : contrôles, preuves et limites.
- docs/evaluation/ : rapports d’évaluation.
