# SOC AegisAI : alertes répétition et erreurs d'agents

## Signaux et seuils de laboratoire

| Règle | Signal | Seuil | Évaluation | Pending |
|---|---|---|---|---|
| aegisai-prompt-repeat | prompt_injection_suspected, groupé par tenant_id + user_id | au moins 3 / 5 minutes | 30 s | 30 s |
| aegisai-agent-failures | agent_call_failed, groupé par target_service | au moins 1 / 2 minutes | 30 s | 0 s |

Les règles existantes d'authentification et de collecte Nginx sont conservées.
Les seuils servent à une démonstration ; ils ne sont pas calibrés sur un trafic industriel.
Un message marqué suspect n'est pas une preuve définitive d'attaque. Une erreur de
service n'est pas attribuée automatiquement à une intention malveillante du client.
Aucun compte n'est bloqué automatiquement et aucune notification externe n'est configurée.

## Événement agent_call_failed

Les trois clients inter-services journalisent un événement lorsque leur appel lève
une HTTPException 5xx. Les 502 sont classées invalid_agent_response, les 503
agent_unavailable, et les autres HTTPException 5xx agent_call_error. Les refus 422
ne sont pas traités comme des pannes. Les exceptions Python inattendues restent
couvertes par les erreurs HTTP génériques, sans classification agent exhaustive.

Le JSON comprend une date, le nom de l'agent cible, la ressource, tenant_id, user_id,
trace_id, statut et raison bornée. Il n'inclut ni body, ni mot de passe, ni jeton,
ni texte brut de l'exception. L'événement HTTP server_error existant porte la même trace.
Le signal agent est conservé dans Loki ; la table d'audit existante reçoit l'événement
HTTP. Aucun nouveau stockage métier ni changement de droits SQL n'est introduit.

L'absence de trafic pendant une panne ne produit pas agent_call_failed : il s'agit
d'une détection d'échec à la demande, pas d'une sonde active permanente de chaque agent.

## Attribution sans indexer les identités

Alloy continue d'indexer seulement les labels déjà utilisés, dont service, event_type
et status_code. tenant_id et user_id sont extraits du JSON à la requête LogQL.
Ils deviennent des dimensions de calcul et d'alertes, sans devenir des labels de
streams indexés dans Loki. Le regroupement par compte reste adapté au laboratoire ;
il faut revoir sa cardinalité pour un grand déploiement.

## Investigation BWS

1. Ouvrir Grafana avec soc_admin et le dossier AegisAI SOC.
2. Dans Alerting > Alert rules, examiner le nom de la règle, ses labels et sa santé.
3. Ouvrir AegisAI — Agents & Security Signals, le nouveau dashboard.
4. Déplier les lignes du panneau d'instructions suspectes ou d'échecs agent.
5. Copier un trace_id, puis utiliser Grafana Explore avec Loki, par exemple :

```logql
{job="aegisai"} |= "TRACE_UUID_OBSERVE"
```

TRACE_UUID_OBSERVE est à remplacer par une trace réellement observée, sans supposer
qu'un identifiant du tutoriel existe dans les données.

Pour une panne, vérifier target_service, reason et l'erreur HTTP de même trace.
Vérifier ensuite le service Docker, la configuration réseau, TLS et la réponse attendue.
Pour une détection répétée, vérifier le tenant et le compte authentifié, le nombre de
refus et les faux positifs éventuels avant toute qualification d'incident.

Le compte applicatif security.admin@bws.example.test et le compte Grafana soc_admin
sont distincts. L'application BWS peut consulter les métadonnées d'audit ; les logs
inter-services détaillés et les alertes se consultent dans la console Grafana.

## Retour Normal et limites d'observation

Les requêtes utilisent des fenêtres glissantes et un zéro de repli lorsque la requête
réussit sans événement. Les erreurs de requête ne sont pas converties en zéro.
Les règles gardent noDataState=NoData et execErrState=Error.

Lorsqu'une série par compte ou par agent sort de la fenêtre, Grafana peut la résoudre
par son mécanisme MissingSeries, puis la retirer de l'interface. Le retour Normal
peut donc signifier seulement que le seuil n'est plus atteint ou que la série a expiré.
Il ne prouve pas à lui seul le rétablissement d'un service ni la bonne santé de la collecte.

Le test de panne vérifie séparément une requête health mTLS après redémarrage.
La règle existante de collecte Nginx aide à détecter certains problèmes de pipeline ;
elle ne constitue pas une surveillance exhaustive de chaque cible de logs.

## Tests reproductibles

- test_agent_observability.py : statut conservé, événement unique, raison bornée,
  absence de détail sensible, pas de faux événement pour un succès ou un 422.
- test_monitoring_helpers.py : le compte B n'est pas attribué à A, un état d'erreur
  ou de démarrage n'est pas considéré comme une réussite, une erreur Loki ne devient pas zéro.
- check_monitoring_queries.py : chaque nouvelle requête est réellement envoyée au Loki déployé.
- check_injection_alert.py : trois vrais refus applicatifs, vérification des traces dans
  Loki, puis cycle d'état Grafana et comparaison SQL des comptes métier/LLM.
- check_agent_failure_alert.py : arrêt temporaire de gas-agent, vrai HTTP 503,
  absence de création métier, redémarrage en finally et probe TLS, puis corrélation Loki
  et cycle d'état Grafana.

Les rapports incluent les transitions et traces réellement observées. Le résultat n'est
passed qu'après les contrôles attendus. Ne pas lancer les deux scénarios en parallèle,
ni d'autres opérations métier du même tenant pendant leurs comparaisons SQL.
La restauration après arrêt suppose que le script peut continuer à s'exécuter ; une
coupure de VM ou un kill forcé peut nécessiter un redémarrage manuel du service.

## Références techniques

- https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/
- https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rule-evaluation/stale-alert-instances/
- https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rule-evaluation/nodata-and-error-states/
- https://grafana.com/docs/loki/latest/reference/loki-http-api/

Les mécanismes documentés ne remplacent pas la validation des versions déployées :
Loki valide ses requêtes à l'exécution et les scripts lisent la définition et l'état
effectifs des règles Grafana avant de conclure.
