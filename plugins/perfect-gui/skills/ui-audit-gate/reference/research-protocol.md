# Protocole de recherche Web

## Obligation

Une recherche est tentée à chaque audit déclenché. En N1, une ou deux requêtes ciblées suffisent. Chaque requête et chaque page ouverte sont consignées avec `research_log.py`. Une référence ne compte que si son URL a été consultée (ou revalidée) dans ce run.

## Confidentialité

Les requêtes décrivent un motif d'interface, jamais le produit : « accessible inline form error pattern » et non « erreur formulaire checkout ACME interne ». Aucune capture, aucun nom de client, aucune URL interne, aucune donnée personnelle. `research_log.py query` refuse les requêtes qui contiennent des adresses e-mail, des hôtes locaux ou privés ou des chaînes qui ressemblent à des jetons, sauf `--force` après vérification.

## Construction des requêtes

Paramètres tirés du contexte : type de produit, tâche, plateforme, composant, design system existant, public **connu** (ne pas en inventer), secteur.

Gabarits :
- `<composant> accessibility pattern` (« date picker accessibility pattern »)
- `<design system reconnu> <composant>` (Material, Apple HIG, Fluent, Carbon, GOV.UK Design System, DSFR pour un service public français, etc.)
- `<norme> <critère> understanding` (« WCAG 2.2 target size minimum understanding »)
- `<tâche> usability research` (sources de recherche UX reconnues)
- Appareils : `<constructeur> <modèle> specifications`, puis la page officielle
- Support d'une API Web : `<API> browser compatibility` (MDN, tables de compatibilité)

## Hiérarchie des sources

| Rang | Type | Usage |
|---|---|---|
| 1 | Normes et documentation officielle (W3C/WAI, WHATWG, MDN, documentation Apple, Android, Microsoft, constructeurs) | Exigences, comportements, support |
| 2 | Design systems reconnus | Patterns éprouvés, anatomie des composants |
| 3 | Recherche UX publiée | Justification d'un comportement |
| 4 | Produits comparables observés | Conventions du secteur |
| 5 | Galeries visuelles | Inspiration seulement, jamais une preuve d'utilisabilité |

## Traçage

```bash
R="$SKILL_DIR/scripts/research_log.py"
python3 $R "$RUN" query --text "WCAG 2.2 focus not obscured understanding" --tool WebSearch --urls https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html
python3 $R "$RUN" visit --url https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html --tool WebFetch
python3 $R "$RUN" ref --json '{
  "titre": "Understanding SC 2.4.11: Focus Not Obscured (Minimum)",
  "url": "https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html",
  "auteur_organisme": "W3C WAI",
  "date_publication_ou_maj": null,
  "statut_consultation": "consultee",
  "rang_source": 1,
  "question_etudiee": "Le pied de page fixe peut-il masquer le focus ?",
  "constats_cles": ["..."],
  "limites_transposition": "Critère AA ; vérifier que le projet vise AA.",
  "utilisee_pour": ["DEF-003"]
}'
python3 $R "$RUN" unavailable --cause "outil de recherche absent dans cet environnement"
```

`ref` refuse une référence `consultee` ou `revalidee` dont l'URL n'apparaît dans aucune requête ni visite du run. La date de consultation est reprise de la visite.

## Comparaison obligatoire

Pour chaque référence retenue, une ligne dans `report.json > comparaisons` :

| Champ | Contenu |
|---|---|
| `ref` | REF-xxx |
| `observation` | Ce que montre notre interface (mesure, capture) |
| `principe` | Ce que la référence établit, dans ses termes |
| `ecart` | Différence constatée |
| `adaptation` | Changement proposé, adapté à notre contexte |
| `benefice` | Bénéfice attendu |
| `nature` | `[EXIGENCE]`, `[HYPOTHÈSE]` ou `[PRÉFÉRENCE]` |

Règles : ne pas copier une interface, ses contenus ou son identité. Ne pas imposer une tendance au détriment de la lisibilité, de la cohérence ou des contraintes métier. Une recommandation normative se vérifie dans sa version applicable. Une ressemblance avec un système conforme ne prouve pas la conformité.

## Pertinence et arrêt

- Retenir une référence si elle répond à une question précise de l'audit, si elle est de rang 1 à 3 (rang 4 pour une convention de secteur) et si elle est transposable à la plateforme.
- S'arrêter quand chaque question ouverte a au moins une référence de rang 1 à 3, ou après deux tours sans information nouvelle.
- Plafond indicatif : 5 références en N1 et N2, 8 en N3. Au-delà, justifier. Retirer les liens qui ne servent à aucun constat.

## Réutilisation

`.ui-audit/research-cache.json` garde les références des runs précédents. Pour en réutiliser une : rouvrir l'URL (WebFetch), consigner la visite, puis `ref` avec `"statut_consultation": "revalidee"`. Une référence citée sans revalidation porte `memoire_non_revalidee` : elle ne compte pas comme recherche du run et ne fonde jamais seule un `[EXIGENCE]`.

## Web indisponible

`research_log.py unavailable --cause ...`, puis `report.json > recherche.statut = "non_realisee"` avec la cause. Poursuivre les contrôles locaux. Étiqueter les recommandations tirées des connaissances internes `[HYPOTHÈSE, non sourcée en ligne]`. La décision est plafonnée à `VALIDEE_PERIMETRE_TESTE`.
