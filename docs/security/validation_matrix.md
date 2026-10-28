# AegisAI — Matrice de validation sécurité

Campagne du 28 octobre 2026.
Environnement : démonstrateur local avec clients, capteurs et données synthétiques.

## Résultats observés

| Scénario | Contrôle vérifié | Résultat | Test / preuve |
|---|---|---|---|
| Requête sans authentification | Authentification obligatoire | HTTP 401 | tests/check_auth.py |
| JWT modifié, expiré, sans expiration ou avec mauvaise audience | Signature et validation des claims | HTTP 401 | tests/check_jwt_security.py |
| Client B demande les données de A | Autorisation et filtrage tenant | HTTP 403 ou 404 selon la route | tests/check_client_role.py |
| Fausse identité administrateur par header | Rôle issu de l’identité authentifiée | HTTP 403 | tests/check_bws_security.py |
| Client demande la supervision BWS | Séparation des permissions | HTTP 403 | tests/check_bws_security.py |
| BWS demande des données ou opérations métier | Supervision limitée aux métadonnées | HTTP 403 | tests/check_bws_security.py |
| Accès à une conversation d’un autre utilisateur, même tenant compris | Propriété de la conversation | HTTP 404 | tests/check_conversation_context.py |
| Plusieurs compteurs correspondent à une question | Clarification avant sélection | Aucun compteur choisi arbitrairement | tests/check_conversation_context.py |
| Changement de ressource dans une conversation | Gestion du contexte serveur | Ancienne analyse non réutilisée | tests/check_conversation_context.py |
| Historique ou champs sensibles fournis par le client | Schéma d’entrée strict | HTTP 422 | tests/check_conversation_context.py ; tests/check_advice_security.py |
| Instruction hostile dans le chat | Contrôle des instructions | HTTP 400 pour les cas testés | tests/check_advice_security.py |
| Réponse « oui » dans le chat | Confirmation via endpoint dédié | Aucune opération métier supplémentaire | tests/check_conversation_context.py |
| Modification d’une confirmation ou d’un statut par le client | Contenu et transitions contrôlés | HTTP 422 | tests/check_client_role.py |
| Exécution sans approbation ou après refus | Workflow de validation | HTTP 409 | tests/check_client_role.py |
| Exécutions concurrentes | Verrouillage et unicité | Une seule tâche, même identifiant retourné | tests/check_client_role.py |
| Conseils eau, énergie et gaz | Catalogue documentaire et mesures autorisées | Sources présentes, aucune analyse créée | tests/check_advice_security.py |
| Connexion aux agents sans certificat client | Authentification mutuelle TLS | Connexion refusée pour les trois agents | tests/check_water_mtls.py ; tests/check_energy_mtls.py ; tests/check_gas_mtls.py |
| Certificat gaz présenté pour un autre nom de serveur | Vérification du nom TLS | Connexion refusée | tests/check_gas_mtls.py |
| Réponse agent altérée | Validation de la réponse | Rejet dans les tests unitaires | tests/test_water_response_controls.py ; tests/test_energy_response_controls.py ; tests/test_gas_response_controls.py |
| Timeout agent simulé | Gestion contrôlée des erreurs | Indisponibilité signalée | Mêmes tests unitaires |
| Trois instructions suspectes du même compte | Corrélation Loki et alerte Grafana | Normal → Pending → Firing → Normal | docs/evaluation/monitoring_injection_20261028T185425Z.json |
| Agent gaz arrêté pendant un appel | Refus contrôlé et supervision | HTTP 503, aucune création métier, redémarrage et probe mTLS réussis | docs/evaluation/monitoring_agent_20261028T190326Z.json |

## Preuves conservées

- Conseils et attaques API :
  docs/evaluation/advice_security_20261028T193100Z.json
- Cycle réel de l’alerte injection :
  docs/evaluation/monitoring_injection_20261028T185425Z.json
- Cycle réel de l’alerte échec agent :
  docs/evaluation/monitoring_agent_20261028T190326Z.json

Les autres résultats de cette campagne ont été observés dans le terminal.
Les fichiers de test décrivent les scénarios ; leur seule présence ne prouve
pas leur exécution. Toutes les sorties ne sont pas archivées automatiquement.

## Interprétation et limites

- Les tests mTLS utilisent les services déployés. Les réponses altérées et
  timeouts sont simulés par des tests unitaires ; ils ne constituent pas
  une interception réseau réelle.
- Les JWT signés avec des claims invalides sont fabriqués par une fixture
  privilégiée. Cela ne signifie pas qu’un attaquant peut signer des tokens.
- Les préfixes de capteurs A-/B- sont une convention des données synthétiques.
  Ils ne remplacent pas une validation indépendante des policies RLS.
- L’alerte agent détecte un échec d’appel. Sans trafic, elle ne constitue
  pas un contrôle actif de disponibilité.
- Le retour d’une alerte à Normal après expiration de sa fenêtre ne prouve
  pas à lui seul la santé du service. Le test gaz vérifie aussi une probe mTLS.
- Les injections refusées démontrent la couverture des cas testés,
  pas une protection universelle contre toute formulation hostile.
- La sélection de plusieurs compteurs a nécessité une adaptation du test :
  clarification, sélection explicite, puis vérification du contexte.
- Les agents utilisent une règle déterministe non calibrée sur des données
  industrielles. Aucun score de fiabilité statistique n’est revendiqué.
- Cette campagne ne constitue ni une certification ni un audit exhaustif.
