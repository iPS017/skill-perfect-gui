# Sévérité, corrections et variantes

## Sévérité (impact sur l'utilisateur)

| Niveau | Définition | Exemples |
|---|---|---|
| `critique` | Empêche une tâche essentielle pour tout ou partie des utilisateurs, sans contournement raisonnable, ou risque de préjudice (perte de données, action irréversible involontaire, clignotement dangereux) | Bouton « Payer » masqué par une bannière, focus piégé, parcours impossible au clavier |
| `majeure` | Gêne fortement la tâche, provoque des erreurs fréquentes ou exclut un groupe, avec un contournement coûteux | Libellé de bouton rogné qui rend l'action ambiguë, erreur de formulaire non annoncée |
| `moderee` | Ralentit ou trouble sans bloquer, contournement simple | Libellé ambigu, alignement visiblement décalé, état vide sans guidance |
| `mineure` | Cosmétique ou cohérence, sans impact mesurable sur la tâche | Espacement hors échelle de 2 px, icône décalée d'1 px |

Facteurs d'ajustement : fréquence (écran principal ou rare), étendue (une instance ou un composant partagé), contournement, population touchée. Un défaut visuel peut être critique s'il masque une action essentielle.

## Quatre champs distincts

| Champ | Valeurs | Sens |
|---|---|---|
| `severite` | critique, majeure, moderee, mineure | Impact |
| `priorite` | P1 (avant validation), P2 (avant mise en production), P3 (backlog) | Ordre de traitement |
| `confiance` | elevee (reproduit et preuve structurelle), moyenne (reproduit, cause supposée), faible (observé une fois ou jugement heuristique) | Solidité du diagnostic |
| `effort` | S, M, L | Coût estimé de la correction |

## Nature

- `[EXIGENCE]` : norme applicable, critère d'acceptation, design system, contrat fonctionnel. Peut bloquer.
- `[HYPOTHÈSE]` : plausible, non démontré. À vérifier ou à assumer explicitement.
- `[PRÉFÉRENCE]` : jugement esthétique. Ne bloque jamais seul.

## Fiche de correction (`report.json > corrections[]`)

```json
{
  "defauts": ["DEF-012"],
  "cause_probable": "Le token --space-btn-x est passé de 16 à 8 px et .btn n'a pas de min-width",
  "cause_etablie": true,
  "solution": "Restaurer min-width dans le composant Button, sans toucher au token utilisé ailleurs",
  "type": "cause_commune",
  "fichiers": ["src/components/Button.css"],
  "composants_affectes": ["Button", "Toolbar", "DialogFooter"],
  "instances_reverifiees": 14,
  "benefice": "Libellés lisibles dans toutes les langues",
  "risques": "Boutons plus larges, retour à la ligne possible dans DialogFooter à 320 px",
  "non_regression": ["CTA-01@320", "CTA-01@pseudo", "GEO-06@DialogFooter", "DS-05@rayon"],
  "autorisation": "dans_perimetre"
}
```

`type` vaut `cause_commune`, `local` ou `palliatif_declare`. `autorisation` vaut `dans_perimetre` ou `proposition_seulement`.

Anti-patterns à refuser ou à déclarer comme palliatifs :
- `overflow: hidden` ou `text-overflow: ellipsis` sur un libellé d'action sans accès au texte complet ;
- `z-index: 9999` sans analyse des contextes d'empilement (`transform`, `opacity < 1`, `filter`, `isolation`, `position` avec `z-index`) ;
- réduire la taille de police d'un composant partagé pour faire tenir un libellé (risque sur les cibles et la lisibilité) ;
- `outline: none` sans indicateur de focus de remplacement ;
- largeur fixe en pixels sur un conteneur de texte traduit.

## Variantes

À proposer seulement s'il existe un arbitrage réel : plusieurs solutions valides avec des compromis différents, ou un conflit entre contraintes. Deux ou trois au maximum.

| Critère | Variante A | Variante B | Variante C |
|---|---|---|---|
| Compréhension | | | |
| Efficacité (étapes, temps) | | | |
| Accessibilité | | | |
| Cohérence avec le design system | | | |
| Complexité d'implémentation | | | |
| Contraintes métier et techniques | | | |
| Qualité visuelle `[PRÉFÉRENCE]` | | | |
| Incertitudes | | | |

Joindre une capture ou un prototype rendu si le coût est raisonnable (une branche ou un fichier temporaire, capturé avec `capture.py`). Recommander une option avec sa justification. Préciser que l'évaluation est heuristique et ne vaut pas un test avec des utilisateurs.
