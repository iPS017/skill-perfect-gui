# Barrière de validation

`verify_report.py` applique exactement ces règles. En cas de doute, c'est le script qui fait foi, et un écart entre le script et ce document est un bug à signaler.

## Statuts de contrôle (`controles[].statut`)

| Statut | Condition | Champs obligatoires |
|---|---|---|
| `reussi` | Méthode entièrement exécutée, résultat conforme, preuve conservée | `preuves` (fichiers existants) |
| `echoue` | Exécuté, non conforme | Au moins une fiche de défaut qui référence le contrôle |
| `non_verifie` | Non exécuté ou non concluant | `raison`, `raison_type` |
| `non_applicable` | Le contexte ne s'y prête pas | `raison` factuelle (« pas de formulaire dans le périmètre ») |

`raison_type` prend l'une de ces valeurs :
- `technique` : outil absent, capture impossible ;
- `humain` : lecteur d'écran réel, jugement de marque, test utilisateur ;
- `appareil_reel` : charnière, clavier natif, capteurs ;
- `hors_perimetre` : réduction de couverture déclarée ;
- `autre`.

`non_applicable` ne sert pas à masquer un `non_verifie`. « Pas eu le temps » n'est pas une raison de non-applicabilité.

## Conditions bloquantes

| Code | Condition |
|---|---|
| B1 | Un défaut `critique` est ouvert (`ouvert`, `echoue_non_resolu`, ou `accepte_exception` : un critique ne peut pas être couvert par une exception) |
| B2 | Un défaut `majeure` de nature `EXIGENCE` est ouvert sans exception valide |
| B3 | Un contrôle fondamental (`config/levels.json`) est absent du rapport, ou `non_verifie` avec un `raison_type` autre que `technique`, `humain` ou `appareil_reel` |
| B4 | PAR-01 (parcours principal) n'est pas `reussi`, en mode complet. `non_applicable` est toléré avec une raison et produit un avertissement. |
| B5 | Changement visuel sans paire avant/après dont la capture « après » existe. Si des corrections ont été appliquées, il faut au moins une capture « après » prise dans un dossier `after-fix-*`. |
| B6 | Une régression introduite par une correction (`introduit_par_correction: true`) est ouverte |

## Décision

```text
si B1 ou B3 ou B4 ou B5 ou B6, ou B2 non couvert par une exception :
    NON_VALIDEE
sinon si mode in {maquette, sans_execution} :
    VALIDATION_LIMITEE
sinon si un défaut majeur EXIGENCE est couvert par une exception :
    VALIDEE_AVEC_EXCEPTIONS
sinon si recherche.statut != "realisee"
     ou un contrôle requis est non_verifie avec raison_type in {technique, hors_perimetre, autre}
     ou couverture_reduite :
    VALIDEE_PERIMETRE_TESTE
sinon :
    VALIDEE_PROTOCOLE_COMPLET
```

Les contrôles `non_verifie` de type `humain` ou `appareil_reel` ne font pas baisser la décision. Ils sont listés dans `verifications_humaines` et dans le message final.

`VALIDEE_PROTOCOLE_COMPLET` signifie que le protocole a été entièrement suivi au niveau requis. Cela ne signifie pas qu'aucun défaut n'existe. Le rapport le rappelle.

## Cohérence vérifiée par le script

- Chaque `reussi` a des preuves dont les fichiers existent (chemins relatifs au run ou absolus).
- Chaque `echoue` est référencé par une fiche de défaut.
- Chaque défaut `corrige` a un `retest.statut = "reussi"` avec des preuves existantes.
- Chaque référence `consultee` ou `revalidee` a son URL dans `research/log.json`. Une URL absente est traitée comme fabriquée et rend le rapport invalide.
- `recherche.statut = "realisee"` exige au moins une référence valide. `non_realisee` exige une cause.
- Une exception exige `acceptee_par`, `date` et une demande explicite de l'utilisateur (`citation`). L'agent ne s'en accorde jamais.
- La décision écrite doit être égale à la décision calculée. `--apply` écrit la décision calculée seulement si tout le reste est cohérent.

## Défauts résiduels et exceptions

- Les défauts modérés et mineurs restants sont listés avec leur priorité. Ils ne bloquent pas, sauf exigence contraire du projet.
- Exception sur un majeur `EXIGENCE` : uniquement si l'utilisateur l'accepte explicitement dans la conversation. Consigner `{"acceptee_par": "utilisateur", "date": "...", "citation": "<ses mots>", "echeance": "..."}`.
- Les exceptions ouvertes sont rappelées aux audits suivants (`.ui-audit/exceptions.json`).
