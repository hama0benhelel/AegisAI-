# Architecture actuelle d’AegisAI

Version documentaire : 28 octobre 2026. Démonstrateur indépendant, données synthétiques.

## Composants et frontières

| Composant | Responsabilité et accès |
|---|---|
| React / Vite | Espace client ou supervision BWS selon le rôle ; JWT en mémoire |
| Nginx | Interface et reverse proxy `/api/` vers FastAPI |
| FastAPI | Identité, autorisations, récupération DB, contexte de conversation et workflow |
| PostgreSQL 17 | Données et journaux ; RLS forcée, contexte tenant transactionnel |
| water-agent | Analyse déterministe eau ; pas d’accès DB ou Groq |
| energy-agent | Analyse déterministe énergie ; pas d’accès DB ou Groq |
| gas-agent | Analyse déterministe gaz ; pas d’accès DB ou Groq |
| simulator | Production horaire synthétique avec identité DB limitée |
| Groq | Routage sémantique et reformulation ; aucun outil métier |
| Alloy / Loki / Grafana | Collecte, stockage des logs, visualisation et alertes |

Les trois agents sont des services séparés. Le backend reste l’orchestrateur :
il sélectionne les données du bon tenant et appelle l’agent de la ressource.
Ce n’est pas un groupe d’agents LLM autonomes négociant ou exécutant des outils.

## Identité et comptes

Les clients A et B ont chacun un compte `client` et leurs propres données.
Un même compte consulte, demande une analyse et valide ses propositions.
Le serveur déduit l’utilisateur et le tenant du JWT vérifié, puis relit le rôle
et l’état actif en base. Les champs tenant ou rôle soumis au chatbot ne sont
pas acceptés comme source d’autorité.

`security_admin` est réservé à `/auth/me`, `/bws/security/audit` et
`/bws/security/llm-calls`. Les données métier lui sont refusées. Une connexion
PostgreSQL distincte, `aegisai_security_reader`, lit les colonnes de supervision
inter-tenants sans les contextes, sorties LLM ou consommations.
Grafana utilise un compte SOC séparé de l’application.

Les anciens rôles viewer, operator et tenant_admin restent compatibles.
Les anciens écrans React Analyses/Audit/LLMJournal/Workflow ne sont plus montés
par `main.jsx`. Ils sont conservés comme historique, pas comme parcours final.
L’endpoint historique `/agents/{resource}/analyze` reste réservé aux rôles
operator/tenant_admin et enregistre directement une analyse ; le rôle client
utilise le parcours de prévisualisation et confirmation du chat.

## Chat : règles, langage et autorisation

1. Authentification puis validation d’un message de 1 à 1000 caractères.
2. Contrôles locaux : instructions suspectes, opérations désactivées, salutations
   et grammaires reconnues.
3. Si nécessaire, routage sémantique Groq vers un plan JSON strict.
4. Validation du plan comme donnée non fiable ; aucune permission n’en découle.
5. Sélection du compteur dans les données autorisées en base.
6. Clarification si plusieurs compteurs correspondent ; aucun choix arbitraire.
7. Lecture, conseils, explication ou prévisualisation selon l’intention.

La version actuelle du routeur est `hybrid-semantic-advice-v6` et celle du prompt
sémantique `semantic-intent-advice-v3`. Le wrapper conversation et le chat
réutilisent une interprétation mise en cache dans la requête.

Le message brut peut atteindre le LLM de routage sémantique. Il n’est donc pas
exact de dire que toute instruction hors périmètre est forcément rejetée avant
tout appel LLM. Le routeur n’a ni historique libre fourni par le client, ni accès
DB, ni outils d’exécution. Les autorisations sont contrôlées indépendamment.

## Contexte de conversation

Les références de compteur, ressource, analyse, confirmation et période sont
stockées côté serveur, avec propriété utilisateur + tenant et expiration à
30 minutes. Un verrou NOWAIT refuse les messages concurrents avec HTTP 409.
Les conversations sont indépendantes, y compris dans un même tenant.
Changer de compteur, ressource ou période invalide les anciennes références
selon le contexte. Eau et gaz partagent m3 : la ressource vient des métadonnées
autorisées, jamais d’une déduction sur l’unité.

« Oui » ou « je confirme » donne une instruction d’utilisation du bouton dédié.
Cela ne confirme ni analyse ni proposition.

## Mesures et simulation

`synthetic_live_v1` produit six compteurs : A/B-SIM-WATER-01,
A/B-SIM-ENERGY-01 et A/B-SIM-GAS-01. Eau/gaz sont en m3, énergie en kWh.
Seules les heures terminées sont insérées. Les valeurs sont reproductibles ;
une contrainte unique et ON CONFLICT évitent les doublons.
Les pointes synthétiques ont des heures fixes, pas une anomalie artificiellement
ajoutée à chaque dernière mesure. Une analyse peut donc être normale.

Le rôle DB simulateur ne peut ni modifier/supprimer les mesures, ni lire les
utilisateurs ou l’audit. Les policies bornent source, tuples tenant/compteur/
ressource/unité, période d’insertion, intervalle et valeur.
Les données historiques démo restent disponibles pour les régressions.

`/readings` retourne les 100 dernières lignes accessibles, pas un inventaire
exhaustif des capteurs. Les cartes de l’interface reflètent cet extrait.
Les lectures journalières dédiées consultent leurs propres lignes en base.

## Agents et transport mTLS

Le backend utilise des URL fixes, un certificat client et une CA locale.
Chaque agent présente un certificat serverAuth avec son nom DNS ; Uvicorn exige
un certificat client signé par la CA de confiance. Les tests vérifient le refus
sans certificat et, pour gaz, le refus d’un nom serveur incorrect.

Le réseau `agents_private` est interne et partagé entre backend et agents.
Les agents n’exposent aucun port hôte, fonctionnent non-root avec filesystem
read-only, capabilities supprimées et limites mémoire/CPU. Ils ne montent que
leur propre certificat/clé/CA ; la clé de la CA reste hors conteneurs.
Ce réseau ne constitue pas une microsegmentation individuelle entre agents.

Les adaptateurs backend imposent timeout de 5 secondes, absence de proxy et
redirections, plafond de 64 KiB et validation des identifiants tenant/trace,
des sources, calculs, classifications et suggestions. Une réponse invalide est
refusée ; une indisponibilité ne déclenche pas un calcul local de remplacement.
Les certificats feuilles durent 90 jours ; renouvellement/révocation ne sont
pas automatisés.

## Règle de consommation

24 mesures horaires consécutives d’un compteur, avec unités cohérentes :
référence = moyenne des 23 premières, seuil = référence × 2.
Si la dernière valeur est strictement supérieure au seuil : high_consumption ;
sinon normal selon la règle `hourly-baseline-v1`.
Sources, dates et limites sont conservées. Pas de cause racine confirmée,
de probabilité calibrée ou de diagnostic industriel garanti.

## Conseils et génération

Les conseils de réduction utilisent un catalogue local de six conseils généraux
revus, deux par ressource. Empreinte SHA-256 approuvée dans le code et structure
stricte ; une altération déclenche un refus. Les textes du catalogue ne sont
pas transmis à Groq. Ce mécanisme suppose le code et son empreinte de confiance
intacts : ce n’est pas une protection après compromission du serveur.

Les sommes aujourd’hui/hier utilisent Decimal, le fuseau Africa/Tunis, les
horodatages disponibles et une indication de couverture complète/partielle.
Le texte exact est rendu localement pour éviter une reformulation numérique
erronée par le LLM. Le routage de la question peut malgré cela appeler Groq.

La dernière mesure et l’explication d’une analyse peuvent utiliser Groq pour
reformuler un contexte structuré autorisé. Schéma JSON, références autorisées,
plafond de réponse et finish_reason sont contrôlés. Quota partagé entre routage
et génération : 5 réservations/minute et 100/24 h glissantes par tenant.
Pas de retry automatique. Quota, sortie invalide ou fournisseur indisponible
entraînent une clarification ou un fallback selon l’étape.
`llm_used=false` décrit la génération de réponse, pas nécessairement le routage.

## Validation humaine et persistance

La prévisualisation d’analyse est figée dans une confirmation de 10 minutes.
La préparation écrit cette demande et son audit, mais aucune analyse.
Le propriétaire confirme/annule via un endpoint dédié. FOR UPDATE, transaction
et états contrôlés rendent les confirmations répétées ou concurrentes idempotentes.

Une suggestion peut devenir une proposition pending liée de façon unique à
l’analyse. Le client approuve ou refuse sa propre proposition, puis déclenche
explicitement la création d’une tâche d’inspection. Approbation requise,
verrouillage et unicité empêchent une double tâche. Aucune commande OT n’est envoyée.

## Audit et supervision

Les événements métier critiques sont écrits avec leur opération dans la même
transaction. L’audit HTTP est séparé et best effort : persisted=false indique
un échec DB. Un Trace ID relie HTTP, événements agents et appels LLM.

Alloy collecte backend, frontend, trois agents, SSH et fail2ban ; pas le
simulateur actuellement. Les identités/Trace IDs ne sont pas des labels indexés
Loki : ils sont extraits lors des requêtes. Les chemins Docker générés sont à
actualiser après recréation des conteneurs. Aucun Docker socket monté.

Alertes : refus d’authentification répétés, absence de logs healthcheck Nginx,
au moins trois instructions suspectes par compte/tenant sur 5 min avec pending
30 s, et au moins un échec d’appel agent sur 2 min. Notifications externes non
configurées. L’alerte agent exige un appel ; le retour à Normal par expiration
d’une fenêtre ne constitue pas une probe de disponibilité.

## Réseaux et conservation

Réseau applicatif : backend, DB et simulateur ; agents sur réseau interne dédié.
Monitoring dispose d’un réseau interne et d’un réseau UI pour Loki/Grafana.
Ports hôte 8000/8080/3000/3100 limités à localhost ; accès Mac par tunnel SSH.
Le frontend et les liens DB internes ne sont pas configurés en TLS de bout en bout.

Loki : rétention configurée à 72 h ; Docker : json-file 10m × 3 par service.
Les fichiers SSH/fail2ban tournent selon logrotate hôte. PostgreSQL n’a pas de
purge automatique des journaux/conversations ; expiration d’accès et effacement
physique sont deux notions différentes.
