# Exploitation et livraison du démonstrateur

## État attendu

La VM déjà configurée contient les migrations 001 à 016, les comptes de
simulation et sécurité, `.env` privé et la PKI hors dépôt. Les scripts de création
de comptes et certificats sont des scripts de préparation, pas de redémarrage.
Ne pas les relancer pour corriger une erreur de login. Ne jamais réappliquer
automatiquement toutes les migrations sur la base existante : elles ne sont
pas idempotentes et aucun registre de migration n’est livré.

Le bootstrap vierge n’a pas été validé de bout en bout. `01-init.sh` crée le rôle
app/schéma au premier démarrage PostgreSQL, pas l’ensemble du système. Certaines
préparations nécessitent des variables locales et un backend déjà démarré.
`.env.example` est une liste de variables, pas un installateur automatique.

## Redémarrage et maintenance courante

Depuis le dépôt :

```bash
sudo -v
bash scripts/aegis.sh config --quiet
bash scripts/aegis.sh up -d
python3 scripts/update_log_targets.py
bash scripts/aegis.sh restart alloy
bash scripts/aegis.sh ps
```

Ne pas utiliser `down -v` : cela supprime les volumes nommés. Ne pas employer
`--remove-orphans` avec une définition Compose partielle.
Ne pas afficher la configuration interpolée complète, qui contient les secrets.

En cas de modification du backend :

```bash
bash scripts/aegis.sh build backend
bash scripts/aegis.sh up -d --no-deps --wait backend
python3 scripts/update_log_targets.py
bash scripts/aegis.sh restart alloy
```

Un redémarrage sans recréation conserve les chemins Docker ; une recréation les
change. Alloy collecte cinq conteneurs : backend, frontend et les trois agents.

## Contrôles après livraison

```bash
curl --max-time 10 -fsS http://127.0.0.1:8080/api/health/ready
curl --max-time 5 -fsS http://127.0.0.1:3000/api/health
curl --max-time 5 -fsS http://127.0.0.1:3100/ready
bash scripts/check_local_controls.sh
bash scripts/aegis.sh exec -T db \
  psql -X -U postgres -d aegisai -v ON_ERROR_STOP=1 \
  < tests/check_database_security.sql
python3 scripts/check_monitoring_queries.py
```

Les contrôles SQL ne modifient ni données, ni comptes, ni policies. Ils exigent
les fixtures A/B et les rôles déjà configurés. Ils contrôlent les flags RLS de
dix tables, les droits des rôles et la visibilité des mesures sous le rôle app.
Ils ne constituent pas une preuve exhaustive de toutes les policies métier.

Les tests locaux sélectionnés utilisent des mocks : pas de requête Groq ou DB
réelle. Ils s’exécutent dans des processus backend distincts avec leur sortie
sur le terminal. Ils ne simulent pas un incident via l’API en production.

Les contrôles mTLS contre les services déployés :

```bash
for resource in water energy gas; do
  bash scripts/aegis.sh exec -T backend python - \
    < "tests/check_${resource}_mtls.py" || exit 1
done
```

Le scénario courant de frontière Groq est `python3 tests/check_client_llm_boundaries.py` :
les refus locaux ne réservent aucun appel, la lecture autorisée conserve ses sources.
Il accepte le mode désactivé ou fallback et n’exige donc pas une génération réelle.
Les anciens `check_llm_boundaries.py` et `check_rbac.py` sont historiques : leurs
hypothèses peuvent précéder le routeur sémantique et le rôle client.

Les scripts API demandent les mots de passe avec getpass. Les tests client,
contexte et workflow créent des données synthétiques d’évaluation. Les tests
Groq réels consomment le quota partagé routage/génération. Une clarification
pour quota ne signifie pas un défaut de séparation des tenants.

## Compatibilité historique

Les données A/B-WATER-01 et A/B-ENERGY-01 et comptes viewer/operator/admin restent
nécessaires à certains tests historiques. Les migrations anciennes sont conservées
pour décrire l’évolution du schéma. Ne pas supprimer en bloc les données ou
réécrire une migration déjà appliquée. Les évolutions destructives nécessiteraient
une migration dédiée et une revue de toutes les références.

Les scripts `build_security_alerts.py` et `build_security_dashboard.py` reconstruisent
les anciens fichiers provisioning. Ils ne sont pas requis au redémarrage.
Les nouveaux fichiers agents/sécurité sont provisionnés séparément et ne doivent
pas être écrasés par une génération non revue.

## Certificats et clés

PKI : `/home/bws/.local/share/aegisai-pki`. La clé CA reste dans authority.
Le backend monte backend ; chaque agent monte uniquement son sous-dossier.
Les clés feuilles sont lisibles par l’UID 10001 utilisé dans les conteneurs.
Ne jamais monter authority dans un service ni committer son contenu.
Les scripts de génération refusent normalement d’écraser les éléments existants.
Renouvellement et déploiement de nouveaux certificats restent des opérations
manuelles à préparer avant expiration ; ne pas régénérer la CA pendant une démo.

## Démonstration courte

1. Client A : dernière mesure et consommation d’hier d’un compteur simulé.
2. Demande d’analyse : prévisualisation, puis confirmation par bouton.
3. Expliquer l’analyse ; si suggestion disponible, créer/valider/exécuter la proposition.
4. Client B : tentative sur une référence A refusée.
5. BWS sécurité : retrouver une tentative par tenant/utilisateur et Trace ID.
6. Montrer les rapports des cycles d’alertes déjà exécutés.

Une analyse normale ne propose pas forcément de tâche. Les pointes synthétiques
sont à heures fixes ; utiliser une fixture documentée pour le scénario anomalie.
Pour rejouer une panne ou un cycle SOC, suivre le runbook ; ces tests ont un effet
sur les services et durent plusieurs minutes. Ne pas les exécuter en parallèle.

## Livraison Git

Sur la VM, après application et checks réussis :

```bash
git status -sb
git diff --check
git fetch origin
git log --oneline origin/main..HEAD
```

Versionner uniquement les fichiers revus. Le script local de backup et le rapport
injection 184612Z restent hors livraison selon le choix du projet.
Aucun `git add .`, force push, réécriture d’historique ou suppression de branche
n’est nécessaire pour cette livraison.

Quand la branche finale est commitée et poussée, sans modification suivie locale :

```bash
git switch main
git merge --ff-only origin/main
git merge --no-ff feat/client-experience -m "Merge validated AegisAI client and agent platform"
```

Si une commande échoue ou si un conflit apparaît, arrêter la séquence et examiner
le conflit ; ne pas forcer. Si le dépôt impose une PR, utiliser cette branche
comme source et main comme cible. Pas de contournement de protection de branche.

Après merge, vérifier les endpoints de santé et le parcours client sur la version
locale finale. Pousser seulement après succès :

```bash
git push origin main
git status -sb
```

Un tag de version peut ensuite identifier le commit présenté au jury. Le rapport
académique est préparé après stabilisation et livraison, en réutilisant les preuves
et limites documentées ; une perspective ne doit pas être présentée comme livrée.
