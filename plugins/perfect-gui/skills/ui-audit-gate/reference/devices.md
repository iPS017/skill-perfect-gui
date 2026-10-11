# Appareils nommés et classes d'écran

## Règle

Aucune dimension, disponibilité ou capacité d'appareil ne vient de la mémoire. Quand un appareil est nommé (par l'utilisateur ou par un brief) :

1. Chercher la page officielle du constructeur et, si utile, sa documentation développeur.
2. Relever, avec la date de consultation : appellation exacte, disponibilité, taille et définition des écrans, navigateur par défaut, capacités Web exposées (segments, posture).
3. Convertir en pixels CSS seulement si la source donne la définition et le facteur d'échelle, ou si un profil d'émulation officiel existe (profils d'appareil de Playwright ou de Chrome DevTools, en citant la version). Sinon, raisonner par classe d'écran.
4. Consigner la source avec `research_log.py ref`.

Si le nom ne correspond à aucun produit vérifiable, le rapport le dit et raisonne par classe d'écran. Exemple : « Apple Duo » ne correspond à aucun produit qu'on puisse confirmer comme établi. Le « Surface Duo » de Microsoft est un appareil double écran distinct, à rapprocher seulement si une source le confirme et si c'était l'intention. « Samsung Z Flip » désigne une gamme de pliables à clapet (Galaxy Z Flip) dont le modèle et la génération sont à préciser et à vérifier.

## Classes d'écran

| Classe | Caractéristique | Ce qu'on peut émuler | Ce qui demande un appareil |
|---|---|---|---|
| Mobile étroit | Environ 320 à 360 px CSS | Largeur, DPR, tactile | Clavier natif, barres système |
| Mobile courant ou large | Environ 375 à 430 px CSS | Idem | Idem |
| Pliable à clapet fermé | Petit écran externe | Taille si sourcée | Disponibilité réelle d'un navigateur sur cet écran |
| Pliable à clapet ouvert | Écran très allongé | Taille si sourcée | Pliure, posture |
| Pliable livre fermé | Écran étroit et haut | Taille si sourcée | Changement d'écran actif |
| Pliable livre ouvert | Quasi carré, proche d'une tablette | Taille si sourcée, transitions de largeur | Charnière, posture, continuité de l'app |
| Double écran | Deux surfaces séparées | Segments si le navigateur les expose | Charnière physique |
| Tablette | Environ 768 à 1180 px CSS | Largeur, orientation | Clavier natif, stylet |

## Transitions de pliage en émulation

Une transition se reproduit comme un redimensionnement en cours d'usage :

```bash
python3 "$SKILL_DIR/scripts/resize_probe.py" --url URL --mode state \
  --widths <fermé>,<ouvert>,<fermé> --height <hauteur> --actions etat-en-cours.json
```

Le rapport précise `fidelite: emulation` et marque la charnière, la posture semi-pliée et le changement d'écran physique `non_verifie` avec `raison_type: appareil_reel`.
