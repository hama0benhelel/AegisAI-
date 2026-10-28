# Revue de préparation à la livraison

Date : 28 octobre 2026.
Source reçue : archive Git du commit 464d224032192fa93cd717c791684f01dfcc167a.
Cette revue ciblée ne constitue pas un audit exhaustif ou une certification.

## Corrections

- Génération Groq : une enveloppe JSON non objet pouvait provoquer une exception
  au lieu du fallback. Validation explicite de l’enveloppe, choices, message et
  content ; le journal est terminé en fallback pour les formes invalides testées.
- Routeur Groq : même validation de la structure imbriquée avant utilisation.
- Tests eau/énergie : variables TLS fictives fournies dans les mocks, sans dépendance
  aux chemins/certificats de la VM. Les validations TLS réelles restent séparées.
- Test du routeur : version de prompt attendue actualisée explicitement.
- Régression supplémentaire : les sommes journalières contournent la génération
  et conservent exactement leur texte et leurs sources.

Pas de modification de migration, données, rôles, mots de passe, certificats,
policies ou catalogue approuvé. Les comptes historiques restent pour compatibilité
avec les tests, avec cette limite explicitement documentée.

## Vérifications effectuées sur la copie de travail

- 62 tests locaux backend/helpers réussis, dans 11 fichiers ; réseau et DB simulés.
- 2 tests de contrat gaz réussis avec TestClient dans un environnement reproduisant
  le layout de l’image ; pas de test TLS dans ce TestClient.
- 4 tests du producteur synthétique réussis.
- Build frontend réussi avec le lockfile fourni, npm ci offline et Vite 7.3.6.
- Syntaxe Python, JSON, shell et SQL principal contrôlée.

Le contrôle syntaxique SQL ne valide pas l’exécution des blocs PL/pgSQL ni l’état
réel de PostgreSQL. Aucun Docker, Loki ou Grafana local n’a été utilisé pour ces
nouveaux contrôles. Les rapports réels SOC/API déjà fournis restent les preuves
VM des campagnes antérieures.

## À exécuter sur la VM avant merge

1. Construire et redéployer backend avec les deux validations fournisseur.
2. Exécuter scripts/check_local_controls.sh sur le backend reconstruit.
3. Exécuter tests/check_database_security.sql en transaction read-only.
4. Exécuter tests/check_client_llm_boundaries.py et conserver son rapport.
5. Vérifier readiness via frontend et requêtes monitoring.

Si ces étapes passent, versionner les fichiers revus puis intégrer la branche
validée à main selon docs/operations.md. Ne pas présenter les étapes ci-dessus
comme déjà exécutées avant réception de leurs résultats.

## Résultats reçus après déploiement
- Les 62 contrôles locaux sélectionnés ont réussi.
- Le contrôle SQL read-only a validé les privilèges, FORCE RLS,
  l’absence de mesures sans contexte et l’isolation A/B.
- Les sept refus API testés n’ont réservé aucun appel LLM.
- La lecture autorisée a conservé ses sources avec une réservation.
- La readiness via Nginx et les dix requêtes Loki ont réussi.

Preuve API :
docs/evaluation/client_llm_boundaries_20261028T195722Z.json

Ces résultats complètent les étapes précédemment indiquées comme
à exécuter. Ils ne constituent pas une validation d’installation vierge.
