# Couche de sécurité — état et limites

État documentaire : 28 octobre 2026. Référence des scénarios et preuves :
[matrice de validation](security/validation_matrix.md).

## Modèle de confiance

La menace étudiée est un utilisateur malveillant ou une réponse externe non
fiable dans un démonstrateur multi-tenant. Le backend vérifie les permissions
avant accès métier ; un plan LLM ne constitue jamais une autorisation.
L’hôte, la configuration du backend, la CA et les superusers DB restent des
composants de confiance. Le backend détient aussi le secret du lecteur sécurité :
la séparation DB limite les usages normaux, pas une compromission complète du backend.

## Contrôles

| Frontière | Contrôle | Limite à présenter |
|---|---|---|
| Authentification | JWT HS256 : signature, issuer, audience, iat/exp, utilisateur actif ; Argon2id | Pas de refresh ou révocation individuelle ; durée 15 min |
| Rôle | Lu en DB, pas depuis un header client | Comptes historiques encore actifs selon la VM |
| Client A/B | Filtres API et contexte transactionnel sous RLS forcée | Le rôle applicatif peut définir le contexte ; une compromission du backend dépasse cette garantie |
| Supervision BWS | Allowlist endpoints et rôle DB lecture de colonnes limitées | Métadonnées inter-tenants intentionnellement visibles |
| Conversation | Tenant + propriétaire, 30 min, verrou NOWAIT | Expiration sans purge physique automatique |
| Confirmation | Propriétaire, contenu figé, expiration, transaction et verrou | Préparation écrit déjà une demande/audit ; le calcul de prévisualisation a déjà lieu |
| Proposition/tâche | Approbation et exécution distinctes, unicité/idempotence | Le client peut être auteur et approbateur ; pas de commande physique |
| Agent réseau | mTLS, noms DNS, URL fixe, redirections/proxy refusés | CA commune, réseau partagé ; pas de révocation/rotation automatisée |
| Réponse agent | Tenant/trace/sources/calculs/suggestion contrôlés | Cas altérés couverts par mocks ; pas une campagne MITM réelle |
| Langage | Règles locales puis routeur JSON strict, autorisation indépendante | Pas de garantie universelle anti-injection ; un message inconnu peut atteindre le LLM de routage |
| Génération Groq | Contexte autorisé, JSON, source_ids, limites, fallback | Des références valides ne prouvent pas chaque assertion |
| Conseils | Catalogue local revu, hash et schéma contrôlés | Protection suppose empreinte/code non compromis ; pas un RAG documentaire ouvert |
| Totaux journaliers | Sommes Decimal, couverture et texte déterministes | Données synthétiques, pas une facture ni une mesure temps réel |
| Quotas Groq | Réservation sérialisée par tenant : 5/min et 100/24 h | Limite d’appels, pas budget monétaire ou limite exacte de tokens |
| Audit | Métadonnées sans credentials ; opérations critiques atomiques | HTTP best effort ; pas WORM contre superuser |
| Supervision | Logs corrélés et alertes observées Firing puis Normal | Pas de notifications externes ; collecte indispensable |
| SSH/fail2ban | Clé SSH, password/root désactivés, ban manuel vérifié | Déclenchement automatique après échecs réels non démontré |

## Identités PostgreSQL

- `aegisai_app` : accès applicatif sous RLS, pas de superuser/BYPASSRLS.
- `aegisai_security_reader` : métadonnées audit/LLM, défaut read-only ; aucune
  lecture de consommation, input_context ou output_text.
- `aegisai_simulator` : lecture/insertion des tuples synthétiques autorisés ;
  pas d’UPDATE/DELETE, ni lecture users/audit.

L’application ne peut pas UPDATE/DELETE audit_events. Les rôles superuser restent
capables de modifier les journaux. Les tests API A/B ne remplacent pas les tests
SQL sous rôle applicatif. `tests/check_database_security.sql` permet une revue
read-only des privilèges et une vérification RLS sur la base préparée.

## Appels LLM et données transmises

Distinguer routage sémantique et génération :

- Routage : message courant brut, pas d’historique client arbitraire ni contexte
  DB ; journal local digest/longueur et plan obtenu.
- Génération : faits et sources autorisés, texte de référence et limites.
- Conseils et totaux journaliers : pas de génération LLM ; leur routage peut en
  utiliser un si le message n’est pas reconnu localement.

Les réponses fournisseur malformées sont traitées comme invalid_output :
clarification ou réponse de secours, sans retry. Une réservation est comptée
même en cas d’échec. Les tokens inconnus restent NULL ; un appel interrompu peut
rester started. Les interfaces BWS excluent les contenus sensibles du journal.
Ni le catalogue ni la DB ne sont accessibles directement au fournisseur.

## Preuves et portée

Les rapports datés conservent les tests API conseils et les cycles réels
injection/panne gaz. Les contrôles mTLS ont été exécutés contre les services du
lab. Les réponses altérées, délais réseau et erreurs fournisseur sont testés
avec mocks ; leur réussite ne démontre pas une attaque réseau en conditions réelles.
Les tests de JWT invalides signés utilisent une fixture administrateur locale.

Les chiffres V1/V2 dans docs/evaluation sont des évaluations historiques du gate
sur corpus de développement. Ils ne mesurent pas la performance globale du
routeur hybride courant ni une détection générale sur attaques inédites.

## Conservation et exploitation

Logs Docker : 10m × 3 par conteneur ; Loki : 72 h configurées. Audit, sorties LLM,
conversations et analyses PostgreSQL n’ont pas de purge automatisée. Ne pas
annoncer de conservation illimitée garantie, de minimisation complète ou de droit
à l’effacement implémenté. Ne pas committer dumps, credentials ou clés privées.

Les ports sont limités à localhost et accessibles par tunnel SSH sur la VM.
Nginx ne sert pas HTTPS dans ce lab ; les liens DB internes ne sont pas TLS.
Le mTLS inter-agents ne signifie pas TLS 1.3 démontré de bout en bout.

## Fonctionnalités hors périmètre livré

- Apprentissage ML industriel et scores de confiance calibrés.
- Cause racine validée, plans avec dates/responsables, ROI/payback.
- Commande directe des équipements ou exécution autonome d’un plan.
- Upload intelligent, RAG ouvert et base d’expertise propriétaire BWS.
- Facturation et simulateur commercial de tokens.
- Chiffrement applicatif AES-256, LUKS et conformité GDPR/IEC 62443 démontrés.
- Déploiement vierge entièrement automatisé et validé.

Ces points doivent être présentés comme perspectives, pas comme contrôles livrés.
