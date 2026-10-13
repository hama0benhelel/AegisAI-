# Architecture du démonstrateur AegisAI

## Objectif et périmètre

AegisAI est un prototype indépendant inspiré des exigences de sécurité
et de gouvernance de Be Wireless Solutions.

Il utilise des organisations, compteurs et mesures synthétiques.
Les modules agents sont intégrés au même backend FastAPI.
Ils ne sont pas déployés comme agents distribués avec authentification
réseau individuelle ou certificats mTLS.

## Composants

| Composant | Responsabilité |
|---|---|
| React | Interface utilisateur |
| Nginx | Sert l’interface et transmet les appels /api/ |
| FastAPI | Authentification, autorisation et opérations |
| PostgreSQL | Données, isolation RLS et journaux |
| Groq | Formulation de réponses à partir du contexte autorisé |
| Alloy | Collecte des logs |
| Loki | Stockage central des logs |
| Grafana | Dashboard SOC et évaluation des alertes |
| Fail2ban | Protection SSH par règles de bannissement |

## Flux d’une lecture via chatbot

1. L’utilisateur envoie un message et sélectionne un compteur.
2. Nginx transmet la requête à FastAPI.
3. Le backend vérifie le JWT et l’utilisateur actif.
4. Le gate classe le message dans une intention autorisée.
5. Le backend récupère uniquement les données du tenant authentifié.
6. Le contexte tenant PostgreSQL est défini pour la transaction.
7. Le backend réserve un appel LLM si la quota le permet.
8. Groq reçoit un contexte structuré et une instruction système fixe.
9. Le backend vérifie la structure et les références de la réponse.
10. Le résultat et les métadonnées de l’appel sont journalisés.
11. La réponse est présentée avec ses sources.

Dans l’intégration actuelle, le message utilisateur brut et l’historique
de conversation ne sont pas transmis à Groq.

Le fournisseur ne dispose ni d’accès direct à la base ni d’outils
permettant d’approuver ou d’exécuter une opération.

## Identité et isolation

Le tenant provient du compte vérifié par le backend.

- Client A possède ses données et ressources.
- Client B possède ses données et ressources.
- Les contrôles API et PostgreSQL RLS limitent leur visibilité.
- Le contexte tenant est local à la transaction.

Un administrateur de tenant ne possède pas de droits globaux
sur les autres organisations.

## Rôles

| Rôle | Responsabilités |
|---|---|
| viewer | Consultation des ressources accessibles |
| operator | Consultation, analyses et préparation de propositions |
| tenant_admin | Opérations operator, décisions et journaux du tenant |

Après approbation, operator et tenant_admin peuvent créer une tâche.
La séparation obligatoire entre auteur et approbateur n’est pas appliquée.

## Agents eau et énergie

Chaque analyse nécessite 24 mesures horaires consécutives
avec des unités cohérentes.

- Référence : moyenne des 23 premières valeurs.
- Seuil : deux fois cette moyenne.
- Dernière valeur strictement supérieure au seuil : high_consumption.
- Sinon : normal selon cette règle.

Le résultat conserve la version de règle, la date des données,
les valeurs, les sources et les limites.

Aucune cause racine n’est confirmée.
Aucune probabilité de confiance calibrée n’est calculée.

## Confirmation personnelle via chatbot

Une demande d’analyse prépare une prévisualisation figée.
Elle ne crée pas encore de ligne dans la table analyses.

La demande de confirmation :
- appartient à un utilisateur et un tenant ;
- expire après 10 minutes ;
- conserve le résultat et les sources de la prévisualisation ;
- refuse la modification de son contenu ;
- peut être confirmée ou annulée par son propriétaire autorisé.

La confirmation crée l’analyse dans la même transaction
que le changement de statut et les événements métier.
Un verrou évite plusieurs analyses lors de confirmations concurrentes.

La page Analyses conserve un lancement explicite qui enregistre
directement une analyse. La confirmation en deux étapes concerne le chat.

## Approbation des propositions

Une analyse peut fournir une suggestion d’inspection.

1. Un operator ou tenant_admin crée une proposition pending.
2. Un tenant_admin approuve ou rejette la proposition.
3. Une proposition approuvée peut être exécutée.
4. L’exécution crée une tâche d’inspection unique.

La tâche est un enregistrement opérationnel.
Elle ne commande aucun équipement et ne prouve pas que l’inspection
a été réalisée.

## Intent gate

Version : bounded-grammar-fr-en-v2.

Intentions actives :
- q_and_a ;
- anomaly_follow_up ;
- recommendation_request.

Configuration, navigation et action_plan_update sont dans la taxonomie,
mais leurs fonctionnalités ne sont pas activées dans le chat.

La classification utilise une grammaire limitée et des règles
d’instructions suspectes. Des formulations légitimes peuvent être rejetées.

## Génération LLM

Fournisseur : Groq.
Modèle : openai/gpt-oss-20b.
Prompt : grounded-summary-v2.

Lecture et explication peuvent utiliser le LLM.
Refus, clarifications et prévisualisations restent déterministes.

Limites imposées par le backend :
- endpoint fournisseur fixe ;
- contexte maximal de 16 000 octets ;
- génération limitée à 768 tokens ;
- timeout réseau de 15 secondes ;
- un seul essai, sans retry automatique ;
- validation JSON et références de sources autorisées.

Ces validations ne garantissent pas la véracité de chaque assertion.

## Quota et défaillances LLM

Par tenant :
- 5 réservations par minute ;
- 100 réservations sur 24 heures glissantes.

Une réservation échouée compte dans la quota locale.
La réservation est enregistrée avant l’appel fournisseur.

En cas de quota dépassée, panne fournisseur ou sortie invalide,
le backend retourne une réponse déterministe signalée comme fallback.

Les tokens non communiqués restent NULL.
Un fallback après appel fournisseur peut avoir consommé des tokens.
Une interruption du processus peut laisser un appel au statut started.

## Journaux applicatifs

audit_events conserve les événements d’accès et métier.
llm_calls conserve les métadonnées, le contexte et le résultat des appels.

Les interfaces tenant_admin exposent uniquement les données de leur tenant.
L’endpoint du journal LLM exclut input_context et output_text.

Le Trace ID relie une requête HTTP aux événements et appels correspondants.

## Collecte et supervision

Alloy collecte :
- logs Docker du backend ;
- logs Docker de Nginx ;
- lignes SSH d’auth.log ;
- logs fail2ban.

Les fichiers sont montés read-only.
Le Docker socket n’est pas monté.

Les chemins backend/frontend doivent être actualisés après recréation
avec scripts/update_log_targets.py, puis Alloy doit être redémarré.

Loki reçoit les logs et Grafana fournit une console SOC centrale.
Grafana possède un compte distinct des utilisateurs AegisAI.

## Réseaux et accès

- Réseau applicatif Docker pour les services de l’application.
- Réseau monitoring interne pour les échanges de supervision.
- Réseau monitoring_ui supplémentaire pour Loki et Grafana.
- Ports 8000, 8080, 3000 et 3100 publiés sur localhost de la VM.
- Aucun port PostgreSQL publié sur l’hôte.
- Accès depuis le Mac par tunnel SSH.
- SSH accessible sur port 22 et authentification par clé.

Le tunnel SSH protège le transport Mac–VM.
Un certificat HTTPS sur Nginx n’est pas configuré.

## Conservation des logs

| Source | Configuration |
|---|---|
| Loki | Rétention 72 heures, suppression asynchrone |
| Docker | 3 fichiers d’environ 10 MB par container |
| auth.log | Rotation hebdomadaire, 4 archives compressées |
| fail2ban.log | Rotation hebdomadaire, 4 archives compressées |
| PostgreSQL | Pas de purge automatique des journaux implémentée |

Les timestamps Docker proviennent des logs Docker.
Pour SSH et fail2ban, Loki utilise actuellement le temps de lecture ;
le timestamp d’origine reste dans le texte.

## Alertes configurées

- Au moins 5 refus d’authentification en 5 minutes,
  avec condition persistante pendant 30 secondes.
- Absence de healthchecks Nginx dans les logs pendant 2 minutes,
  avec condition persistante pendant 30 secondes.

L’absence de logs peut provenir du service ou de la chaîne de collecte.
Les alertes ne localisent pas automatiquement la panne.
Les notifications externes ne sont pas configurées.
