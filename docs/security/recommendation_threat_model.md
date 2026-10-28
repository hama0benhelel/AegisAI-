# Conseils de consommation : périmètre et preuves de sécurité

## Fonctionnement

Les conseils sont une lecture, distincte du calcul et de l'enregistrement d'une analyse.
Le TAG produit reste recommendation_request ; request_kind=advice distingue le mode conseil.
Le parseur sémantique peut utiliser consumption_advice comme valeur interne ; elle est
convertie côté serveur, sans accorder de permission. Les demandes d'analyse explicites
conservent le workflow de prévisualisation et de confirmation personnelle existant.

Six conseils paraphrasés de ressources publiques ADEME sont distribués avec le backend,
avec leur référence, condition d'application, date de revue et version de catalogue.
La sélection dépend de la ressource autorisée par la DB. Le système ne connaît pas
l'installation du client : ce ne sont ni un diagnostic personnalisé, ni une optimisation
calibrée, ni une garantie d'économie. Le score de fiabilité reste null.

Les conseils ne sont pas reformulés par un LLM. Le routeur Groq peut encore être appelé
pour interpréter une formulation non reconnue localement ; llm_used=false concerne la
génération de la réponse, et ne prouve pas à lui seul l'absence d'appel de routage.
Les formulations du test API sont reconnues localement, et leur absence de réservation
LLM est vérifiée dans la base.

## Frontières de confiance

1. L'identité et le tenant viennent du JWT vérifié et du compte courant en base.
2. Le modèle ne retourne qu'un plan typé ; tenant, rôle, SQL et tool_call sont interdits.
3. Le compteur est résolu dans le tenant. La requête de mesure filtre à nouveau le tenant,
   le compteur et la ressource, sous PostgreSQL FORCE RLS.
4. Le catalogue local est comparé à une empreinte SHA-256 approuvée dans le code.
   Les champs, IDs de conseils et URLs de sources sont limités à un catalogue fermé.
5. Aucun contenu du catalogue n'est envoyé à un modèle ou à un exécuteur d'actions.
   Aucune URL de document n'est téléchargée à l'exécution.
6. Le frontend rend du texte React échappé et limite les liens documentaires à HTTPS
   sur agirpourlatransition.ademe.fr, sans identifiants ni port alternatif.
7. Les conseils n'insèrent ni analyse, confirmation, proposition ni tâche. Les événements
   HTTP d'audit et les métadonnées de conversation restent enregistrés normalement.

## Scénarios reproductibles

| ID | Attaque / contrôle | Protection attendue | Preuve |
|---|---|---|---|
| ADV-01 | Injection utilisateur demandant les autres clients | Refus 400 pour les payloads testés | Test API, trace HTTP |
| ADV-02 | B demande le compteur ou la conversation de A | 404 sans donnée A | Test API |
| ADV-03 | tenant_id / knowledge_document / tool_call fournis par le client | 422, aucune interprétation | Test API et modèle Pydantic |
| ADV-04 | Réponse de gate forcée sur un compteur hors tenant | Requête toujours filtrée sur le tenant et 404 | Test unitaire simulant un gate défaillant |
| ADV-05 | Texte du catalogue remplacé par une instruction hostile | Échec d'intégrité, aucun texte hostile exposé | Test unitaire et copie temporaire de démonstration |
| ADV-06 | URL de source remplacée par une URL de métadonnées ou outil ajouté | Catalogue modifié refusé | Test unitaire |
| ADV-07 | Auteur du document prétend approved=true ou fournit son propre hash | Métadonnées non reconnues, pas de nouvelle autorité | Test unitaire |
| ADV-08 | Catalogue indisponible/altéré pendant un conseil | 503 générique, événement knowledge_integrity_failed | Route testée avec erreur simulée |
| ADV-09 | Demandes de conseils successives | Aucune création métier ni réservation LLM pour les formulations locales testées | Comparaison SQL avant/après |
| ADV-10 | « oui » dans le chat | Clarification, jamais exécution | Test API |
| ADV-11 | Demande explicite d'analyse | Prévisualisation et confirmation toujours exigées | Test unitaire et workflow existant |
| ADV-12 | HTML et lien javascript dans une réponse API de test | Texte échappé, lien non cliquable | Test navigateur avec API simulée |

## Journalisation

recommendations_presented identifie la présentation de conseils, avec le tenant,
l'utilisateur et X-Trace-ID de l'événement HTTP. knowledge_integrity_failed identifie
une indisponibilité de la base de conseils : il ne signifie pas que l'utilisateur ayant
reçu la 503 a compromis le catalogue. Le contenu des conseils et leurs références se
retrouvent via la version déployée ; aucun snapshot individuel complet n'est persisté
par cette étape. Une future traçabilité immuable complète exigerait un stockage dédié.

Les alertes Grafana spécifiques à ces événements ne sont pas créées par ce correctif.

## Limites à présenter au jury

- Catalogue fermé relu, sans téléversement ni ingestion RAG de documents arbitraires.
  Le test de poisoning démontre le refus d'un document local modifié ; il ne prouve pas
  la détection universelle de prompt injection dans une chaîne RAG ouverte.
- SHA-256 suppose le code de vérification et son empreinte approuvée fiables. Un attaquant
  capable de remplacer simultanément le code et le catalogue dépasse cette protection.
  Ce n'est pas une signature cryptographique ni une preuve matérielle d'intégrité.
- La liste de conseils est maintenue par revue de code. Pour une mise à jour légitime,
  revoir le fond, les sources, le JSON et l'empreinte du module dans le même changement.
- Les tests sont des scénarios finis ; ils ne garantissent pas un taux de protection de 100 %.
- La voie conseils ne lance aucune tâche. Les voies métier existantes restent autorisées
  et testées séparément ; elles ne sont pas supprimées par cette protection.
- Les références publiques sont des conseils généraux, pas une base d'expertise propriétaire BWS.
