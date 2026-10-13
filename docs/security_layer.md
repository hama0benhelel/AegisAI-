# Couche de sécurité AegisAI — contrôles et validation

## Périmètre

Prototype indépendant sur données IoT synthétiques, inspiré des
exigences de sécurité et de gouvernance de Be Wireless Solutions.

Le système traite notamment :
- accès non authentifié ;
- JWT falsifié ou expiré ;
- abus de permissions ;
- accès aux ressources d’un autre tenant ;
- contournement de confirmation ou d’approbation ;
- requêtes répétées ou concurrentes ;
- instructions suspectes et demandes hors périmètre ;
- défaillances et sorties invalides du LLM ;
- consommation excessive d’appels LLM ;
- interruption de collecte des logs ;
- accès SSH et tentatives d’authentification.

Les contrôles applicatifs ne garantissent pas la protection après
compromission du serveur ou d’un compte PostgreSQL superuser.

## Contrôles et preuves

| Contrôle | Vérifications réalisées | Limites |
|---|---|---|
| Authentification JWT | Token absent, falsifié, expiré, audience incorrecte et expiration absente refusés | Pas de révocation individuelle ni refresh token |
| Mots de passe | Hashes Argon2id utilisés | Gestion du cycle de vie des comptes limitée |
| RBAC | Viewer et operator refusés sur endpoints administratifs ; faux X-Role ignoré | Auteur et approbateur peuvent être la même personne |
| Isolation | RLS SQL et tests API A/B | Tests sur scénarios synthétiques |
| Rate limiting login | Onzième tentative refusée par HTTP 429 | Mémoire du processus ; utilisateurs derrière Nginx partagent son IP observée |
| Confirmation chat | Propriétaire, tenant, contenu figé, expiration et concurrence vérifiés | Parcours chatbot uniquement |
| Workflow | Approbation requise, rejet non exécutable, tâche unique sous concurrence | Création d’un enregistrement, sans commande OT |
| Intent gate | Corpus d’évaluation et refus via API | Grammaire restrictive et faux rejets possibles |
| LLM | Appels réels, références, JSON, fallback et absence de retry automatique | Structure correcte ne garantit pas les assertions |
| Quota LLM | Limites locales et réservation par tenant | Concurrence de quota non testée de bout en bout sur PostgreSQL |
| Frontière LLM | Demande autorisée journalisée ; demandes refusées sans réservation | Preuve limitée aux scénarios exécutés et au code inspecté |
| Journal LLM | Accès administrateur limité au tenant ; contenu exclu de l’endpoint | Pas de purge automatique des données PostgreSQL |
| Supervision | Logs backend/Nginx corrélés par Trace ID | Mise à jour des chemins après recréation nécessaire |
| Alertes | Déclenchement et retour Normal observés | Notifications externes non configurées |
| SSH | Connexion par clé réussie, password refusé, logs collectés | Clé privée et passphrase à protéger sur le Mac |
| Fail2ban | Ban manuel, règle firewall, Unban et collecte vérifiés | Déclenchement automatique après échecs réels non testé |
| Rotation Docker | Limites vérifiées sur les six containers | Rollover au seuil non forcé pendant les tests |

## Confirmation et approbation

Une demande d’analyse via chatbot prépare une prévisualisation.
Aucune analyse n’est enregistrée avant confirmation.

La confirmation :
- appartient au même utilisateur et tenant ;
- expire après 10 minutes ;
- refuse les champs permettant de modifier le contenu ;
- enregistre le résultat figé de la prévisualisation ;
- crée une seule analyse en cas de confirmations concurrentes.

Les tests ont vérifié :
- refus sans token ;
- refus du viewer ;
- refus d’un autre utilisateur du même tenant ;
- refus d’un autre tenant ;
- refus de contenu supplémentaire ;
- confirmation concurrente et répétée sans duplication ;
- annulation puis confirmation refusée ;
- expiration sans création d’analyse ;
- événements métier enregistrés une seule fois.

La confirmation personnelle d’une demande ne remplace pas
l’approbation d’une proposition par un administrateur.

## Évaluation du gate

Sur le corpus de développement de 34 cas :

| Mesure | V1 | V2 |
|---|---|---|
| Demandes légitimes correctement routées | 7/12 | 11/12 |
| Hors périmètre bloquées | 3/6 | 6/6 |
| Fonctions désactivées bloquées | 4/4 | 4/4 |
| Messages malveillants bloqués | 7/12 | 12/12 |

En V2, 7 des 12 messages malveillants sont explicitement marqués suspects.
Les autres sont rejetés pour d’autres motifs.
Blocage et détection explicite ne constituent pas la même mesure.

Ce corpus a servi au développement et ne prouve pas un taux général
de détection sur des attaques inédites.

L’évaluation sur de nouvelles formulations a également observé
des demandes légitimes rejetées à tort.
Les fichiers dans docs/evaluation/ conservent les résultats détaillés.

## Intégration Groq et contrôles LLM

Le gate, l’authentification et l’accès tenant précèdent la récupération
du contexte et la réservation d’un appel fournisseur.

Le LLM reçoit un contexte structuré, sans message utilisateur brut
ni historique de conversation dans l’intégration actuelle.

Il n’a pas d’accès direct à PostgreSQL et aucun outil d’exécution
ne lui est fourni.

Dix tests isolés ont vérifié :
- utilisation d’une réponse valide avec ses sources ;
- absence d’appel quand le LLM est désactivé ;
- absence d’appel pour une demande de confirmation ;
- fallback lorsque la quota locale est atteinte ;
- fallback sur HTTP 429 sans retry ;
- fallback sur timeout ;
- rejet d’une référence de source inconnue ;
- rejet d’une réponse tronquée ;
- rejet de JSON invalide ;
- refus de réservation lorsque les limites sont atteintes.

Ces tests remplacent les appels réseau et les accès DB par des mocks.

Les tests de frontière sur l’API réelle ont observé :
- un appel autorisé présent dans llm_calls ;
- aucune réservation pour les requêtes sans authentification ;
- aucune réservation pour les messages suspects ou hors périmètre ;
- aucune réservation pour les opérations désactivées ;
- aucune réservation pour tenant forgé ou ressource d’un autre tenant ;
- aucune réservation pour analyse demandée par viewer ;
- clarification sans LLM lorsque le compteur manque ;
- rejet du message trop long ;
- création déterministe d’une analyse sans LLM.

Dans le code actuel, l’appel fournisseur intervient après une
réservation réussie. Ces résultats ne prouvent pas une prévention
universelle des injections de prompt.

## Évaluation du contenu des réponses

Quatre cas synthétiques ont été exécutés, avec une réponse LLM
obtenue pour chacun :
- lecture eau Client A ;
- lecture énergie Client A ;
- explication d’une anomalie eau Client A ;
- explication d’une consommation normale Client B.

Les contrôles techniques exécutés ont validé la présence des sources
et les références retournées.

La revue a relevé une ambiguïté : « 240.000 kWh » dans une réponse
française. Le prompt grounded-summary-v2 demande une notation française
sans décimales inutiles.

Deux appels ultérieurs observés ont produit « 240 kWh ».
Le format des dates et l’indication de timezone peuvent varier.

Cet échantillon ne constitue ni un score de confiance calibré
ni une garantie de justesse de toutes les réponses.

## Journaux et auditabilité

Les événements métier critiques sont écrits dans la transaction
de l’opération correspondante.

L’audit HTTP utilise une écriture séparée. Un échec de persistance
peut être signalé par persisted=false dans les logs.

Le rôle applicatif ne peut ni modifier ni supprimer audit_events.
Un administrateur PostgreSQL peut toujours modifier la base :
le journal n’est pas un stockage WORM immuable.

llm_calls conserve la réservation, le contexte, le résultat final,
le modèle, la version du prompt, la durée et les tokens communiqués.

Un arrêt du processus peut laisser une réservation au statut started.
Un fallback peut avoir consommé des tokens.
Une valeur inconnue est NULL, pas zéro.

L’endpoint du journal LLM :
- est réservé au tenant_admin ;
- filtre les lignes par tenant ;
- exclut input_context et output_text ;
- refuse un tenant différent ;
- limite la taille de l’extrait à 100 lignes.

## Supervision et alertes

Alloy collecte les logs backend, Nginx, SSH et fail2ban.
Loki conserve les logs et Grafana fournit la console SOC centrale.

Les tests ont vérifié :
- corrélation Nginx/backend via le même Trace ID ;
- augmentation des compteurs après requêtes sans token ;
- alerte après refus d’authentification répétés ;
- retour à Normal lorsque les événements quittent la fenêtre ;
- alerte de logs absents après arrêt d’Alloy ;
- retour à Normal après reprise de collecte ;
- connexion SSH par clé visible ;
- Ban et Unban fail2ban visibles.

Les alertes sont visibles dans Grafana.
Aucun canal externe de notification n’est configuré.

Une absence de résultat dans un panneau ne prouve pas la disponibilité
de la chaîne de collecte. Une absence de healthchecks ne localise pas
à elle seule le composant en panne.

## Protection SSH et fail2ban

Configuration SSH effective vérifiée :
- PubkeyAuthentication yes ;
- PasswordAuthentication no ;
- KbdInteractiveAuthentication no ;
- PermitRootLogin no.

Une nouvelle connexion par clé a réussi après reload.
Une tentative de connexion par password a été refusée.

Fail2ban utilise le journal systemd :
- maxretry : 5 ;
- findtime : 10 minutes ;
- bantime : 10 minutes.

L’IP d’administration du Mac, 192.168.64.1, est exclue du bannissement.
La configuration doit être adaptée si cette adresse change.

Le test de 192.0.2.123 a vérifié :
- présence dans Banned IP list ;
- règle REJECT dans f2b-sshd ;
- connexion de cette chaîne à INPUT pour le port 22 ;
- suppression du bannissement après Unban ;
- visibilité des deux événements dans Grafana.

Ce test manuel ne valide pas le déclenchement automatique après
cinq échecs SSH réels.

## Conservation et exposition

Les ports applicatifs publiés sont limités à localhost.
PostgreSQL ne possède pas de port publié sur l’hôte.
SSH écoute sur le réseau.

Le transport Mac–VM utilise SSH.
HTTPS avec certificat sur Nginx n’est pas configuré.

Conservation :
- Loki : rétention configurée à 72 heures, suppression asynchrone ;
- Docker : max-size 10m et max-file 3, appliqués aux six containers ;
- auth.log et fail2ban.log : rotation hebdomadaire avec quatre archives ;
- PostgreSQL : pas de purge automatique des journaux implémentée.

Les limites Docker ont été vérifiées par inspect.
La rotation effective à 10 MB n’a pas été forcée pendant les tests.

## Sauvegarde vérifiée hors livraison Git

Un backup PostgreSQL a été restauré dans une base de test indépendante
sur le même serveur.

Les vérifications ont porté sur :
- nombre de lignes par table ;
- activation et FORCE RLS ;
- policies RLS ;
- propriétaires et SECURITY DEFINER des fonctions ;
- absence de mesures sans contexte tenant ;
- isolation A/B ;
- interdiction de modification et suppression de l’audit par le rôle app.

La base de test a ensuite été supprimée et l’archive copiée sur le Mac.
Le script reste local selon le choix de livraison.

Le dump ne sauvegarde pas les rôles globaux ni les secrets de .env.
L’égalité de chaque valeur de chaque ligne et la restauration sur
une nouvelle VM n’ont pas été validées de bout en bout.

## Incident de duplication de logs observé

Un ancien événement Accepted publickey était présent deux fois dans
auth.log, pour un événement dans le journal systemd.

La configuration inspectée n’a révélé ni double inclusion des règles
ni double processus rsyslog.
Un nouveau test contrôlé a produit une seule ligne, également observée
dans Grafana. La duplication historique n’a pas été reproduite.

La cause reste inconnue et aucun changement rsyslog spéculatif
n’a été appliqué.

## Éléments non implémentés

- Six intentions entièrement fonctionnelles.
- Knowledge base BWS et RAG documentaire.
- Causes racines avec validation d’hypothèses.
- Scores de confiance calibrés en pourcentage.
- Plans avec responsables, dates, ROI et payback.
- Upload intelligent.
- Facturation et simulateur commercial.
- Agents distribués avec mTLS.
- Chiffrement applicatif AES-256 et LUKS démontré.
- TLS 1.3 configuré de bout en bout.
- Gestion complète des droits d’accès et d’effacement.
- Conformité ou certification GDPR/IEC 62443.

Ces éléments restent des limites ou perspectives.
