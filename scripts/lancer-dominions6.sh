#!/bin/bash
# lancer-dominions6.sh - pose par le template AMP TeamKit (recree a chaque Update).
#
#   lancer-dominions6.sh verifier            controle d'installation (etape d'Update)
#   lancer-dominions6.sh cle=valeur ...      demarrage du serveur (ligne de commande d'AMP)
#
# AMP passe chaque reglage sous la forme cle=valeur, entre guillemets : un reglage
# vide reste un argument "cle=" et ne decale jamais les autres. Les valeurs sont
# controlees ici avant d'etre donnees au jeu.
cd "$(dirname "$0")" || exit 1
ICI="$PWD"
JEU="$ICI/jeu"
BIN="$JEU/dom6_amd64"

# Les parties, cartes et mods vont dans donnees/ (dossier de l'instance), pas dans ~/.dominions6.
# Variables relevees dans le binaire (DOM6_CONF, DOM6_SAVE, DOM6_LOCALMAPS, DOM6_MODS).
export DOM6_CONF="$ICI/donnees"
export DOM6_SAVE="$DOM6_CONF/savedgames"
export DOM6_LOCALMAPS="$DOM6_CONF/maps"
export DOM6_MODS="$DOM6_CONF/mods"
mkdir -p "$DOM6_SAVE" "$DOM6_LOCALMAPS" "$DOM6_MODS"

manque_jeu() {
  echo "ERREUR : les fichiers de Dominions 6 sont absents ($BIN introuvable)."
  echo "  - Source SteamCMD : lance Update et connecte un compte Steam qui possede le jeu."
  echo "  - Source manuelle : copie le contenu du dossier steamapps/common/Dominions6 de ton PC"
  echo "    (il contient aussi la version Linux, dom6_amd64) dans le dossier jeu/ de l'instance."
}

if [ "$1" = "verifier" ]; then
  if [ ! -f "$BIN" ]; then
    manque_jeu
    exit 1
  fi
  chmod +x "$BIN"
  absentes=$(ldd "$BIN" 2>/dev/null | grep "not found")
  if [ -n "$absentes" ]; then
    echo "ERREUR : bibliotheques manquantes pour dom6_amd64 :"
    echo "$absentes"
    exit 1
  fi
  echo "Bibliotheques de dom6_amd64 : toutes presentes."
  timeout 20 "$BIN" --version 2>&1 | head -n 3
  # Numeros des nations (pour le reglage des IA), ecrits dans donnees/nations.txt.
  if timeout 30 "$BIN" --listnations --textonly --nosteam > "$DOM6_CONF/nations.txt" 2>&1 && [ -s "$DOM6_CONF/nations.txt" ]; then
    echo "Liste des nations ecrite dans donnees/nations.txt ($(wc -l < "$DOM6_CONF/nations.txt") lignes)."
  else
    echo "Liste des nations : pas obtenue (voir donnees/nations.txt)."
  fi
  if [ -f "$JEU/dom6key" ]; then
    echo "Fichier de cle dom6key : present."
  else
    echo "Fichier de cle dom6key : absent (voir le README si le serveur demande une cle)."
  fi
  exit 0
fi

declare -A V
for a in "$@"; do
  case "$a" in
    *=*) V["${a%%=*}"]="${a#*=}" ;;
    *) echo "ERREUR : argument inattendu : $a" ; exit 1 ;;
  esac
done

refuser() {
  echo "ERREUR : $1"
  echo "Corrige ce reglage dans l'onglet Configuration d'AMP, puis relance."
  exit 1
}
entier() { [[ "$1" =~ ^[0-9]+$ ]]; }

PORT="${V[port]}"
NOM="${V[nom]}"
ERE="${V[ere]:-2}"
CARTE="${V[carte]:-15}"
FICHIER="${V[fichiercarte]}"
TOUR="${V[tour]:-0}"
JOUEURS="${V[joueurs]:-0}"
DEMARRAGE="${V[demarrage]:-0}"
CLIENTS="${V[clients]:-oui}"
IA="${V[ia]}"
NIVEAU="${V[niveauia]:-norm}"
MAITRE="${V[maitre]}"
PLUS="${V[plus]}"

entier "$PORT" && [ "$PORT" -ge 1024 ] && [ "$PORT" -le 65535 ] || refuser "port invalide : '$PORT'."
[[ "$NOM" =~ ^[A-Za-z0-9_-]{1,40}$ ]] || refuser "nom de la partie '$NOM' : 1 a 40 caracteres, lettres sans accent, chiffres, _ ou - (pas d'espace)."
[[ "$ERE" =~ ^[123]$ ]] || refuser "ere '$ERE' : 1, 2 ou 3."
[[ "$CARTE" =~ ^(10|15|20|fichier)$ ]] || refuser "carte '$CARTE' inconnue."
entier "$TOUR" || refuser "delai des tours '$TOUR' : un nombre de minutes."
entier "$JOUEURS" || refuser "joueurs attendus '$JOUEURS' : un nombre."
entier "$DEMARRAGE" || refuser "delai avant le debut '$DEMARRAGE' : un nombre d'heures."
[[ "$CLIENTS" =~ ^(oui|non)$ ]] || refuser "lancement par les joueurs '$CLIENTS' : oui ou non."
[[ "$NIVEAU" =~ ^(easy|norm|diff|mighty|master|imp)$ ]] || refuser "niveau des IA '$NIVEAU' inconnu."
[ -z "$MAITRE" ] || [[ "$MAITRE" =~ ^[A-Za-z0-9_-]{1,40}$ ]] || refuser "mot de passe maitre : lettres sans accent, chiffres, _ ou - seulement (pas d'espace ni de guillemet)."

if [ ! -f "$BIN" ]; then
  manque_jeu
  exit 1
fi
[ -x "$BIN" ] || chmod +x "$BIN"

ARGS=(--tcpserver --textonly --nosteam --statusdump --port "$PORT")
[ "$TOUR" -gt 0 ] && ARGS+=(--minutes "$TOUR")
[ "$CLIENTS" = "non" ] && ARGS+=(--noclientstart)

PARTIE="$DOM6_SAVE/$NOM"
if [ -f "$PARTIE/ftherlnd" ]; then
  # La partie existe deja : on la reprend. Les reglages de creation (ere, carte,
  # IA, mot de passe maitre) sont figes dans la sauvegarde et ne sont pas repasses.
  echo "TeamKit : reprise de la partie $NOM (dossier donnees/savedgames/$NOM)."
else
  echo "TeamKit : partie $NOM pas encore creee, le serveur attend les joueurs (choix des nations)."
  ARGS+=(--era "$ERE")
  if [ "$CARTE" = "fichier" ]; then
    [ -n "$FICHIER" ] || refuser "carte = fichier, mais aucun nom de fichier de carte n'est donne."
    [[ "$FICHIER" == */* || "$FICHIER" == *\\* ]] && refuser "fichier de carte : donne seulement le nom (ex. ma_carte.map), pas un chemin."
    if [ ! -f "$DOM6_LOCALMAPS/$FICHIER" ] && [ ! -f "$JEU/maps/$FICHIER" ]; then
      echo "ATTENTION : $FICHIER introuvable dans donnees/maps/ ni dans jeu/maps/. Depose la carte (.map + images) dans donnees/maps/."
    fi
    ARGS+=(--mapfile "$FICHIER")
  else
    ARGS+=(--randmap "$CARTE")
  fi
  [ "$JOUEURS" -gt 0 ] && ARGS+=(--uploadmaxp "$JOUEURS")
  [ "$DEMARRAGE" -gt 0 ] && ARGS+=(--uploadtime $((DEMARRAGE * 60)))
  for n in ${IA//,/ }; do
    [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -ge 5 ] && [ "$n" -le 499 ] || refuser "nation IA '$n' : un numero entre 5 et 499."
    ARGS+=("--${NIVEAU}ai" "$n")
  done
  [ -n "$MAITRE" ] && ARGS+=(--masterpass "$MAITRE")
fi

# Options en plus, separees par des espaces (une valeur ne peut donc pas contenir d'espace).
read -r -a EN_PLUS <<< "$PLUS"
ARGS+=("${EN_PLUS[@]}")
ARGS+=("$NOM")

AFFICHE=()
for x in "${ARGS[@]}"; do
  if [ -n "$MAITRE" ] && [ "$x" = "$MAITRE" ]; then AFFICHE+=("***"); else AFFICHE+=("$x"); fi
done
echo "TeamKit : dom6_amd64 ${AFFICHE[*]}"

# Utilise seulement par verifier.py : ecrit les arguments du jeu, un par ligne, sans lancer le jeu.
if [ -n "$TK_ESSAI_ARGS" ]; then
  printf '%s\n' "${ARGS[@]}" > "$TK_ESSAI_ARGS"
  exit 0
fi

# Ligne "pret" pour AMP : ecrite quand le port est vraiment ouvert (lu dans /proc/net),
# sans dependre du texte du jeu.
HEX=$(printf '%04X' "$PORT")
(
  TABLES=()
  for t in /proc/net/tcp /proc/net/tcp6; do [ -r "$t" ] && TABLES+=("$t"); done
  for _ in $(seq 1 180); do
    kill -0 $$ 2>/dev/null || exit 0
    if awk -v p=":$HEX" '$4 == "0A" && substr($2, length($2) - 4) == p { t = 1 } END { exit !t }' "${TABLES[@]}"; then
      echo "TeamKit : Dominions 6 ecoute sur le port $PORT (partie $NOM)."
      exit 0
    fi
    sleep 1
  done
  echo "TeamKit : ATTENTION, le port $PORT n'est toujours pas ouvert apres 3 minutes."
) &

# Le serveur ecrit une ligne d'etat chaque seconde ("Setup port ...", "<partie>, Connections ...",
# et la ligne des nations). Ce filtre ne laisse passer une ligne d'etat que si elle a change,
# compte a rebours mis a part ; toutes les autres lignes passent telles quelles. Il coupe aussi
# sur les retours chariot seuls (CR) et convertit le Latin-1 en UTF-8. En Python et pas en awk :
# mawk garde tout en memoire tant que son tampon d'entree n'est pas plein.
FILTRE='
import os, re, sys
TEMPS = re.compile(r"\d+:\d\d(?::\d\d)?|\d+ *(?:seconds?|secs?|minutes?|mins?|hours?)")
NATION = re.compile(r"^\(?\*?[A-Z][A-Za-z]*\)?[?+-]*$")
dernier = dict()
def genre(l):
    if re.match(r"Setup port \d+", l):
        return "setup"
    if re.search(r", Connections \d+", l):
        return "partie"
    m = l.split()
    if len(m) >= 2 and all(len(x) <= 8 and NATION.match(x) for x in m):
        return "nations"
    return None
def sortir(brut):
    try:
        l = brut.decode("utf-8")
    except UnicodeDecodeError:
        l = brut.decode("latin-1")
    g = genre(l)
    if g:
        cle = TEMPS.sub("#", l)
        if dernier.get(g) == cle:
            return
        dernier[g] = cle
    sys.stdout.buffer.write(l.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()
reste = b""
while True:
    bloc = os.read(0, 65536)
    if not bloc:
        break
    morceaux = re.split(rb"\r\n|\r|\n", reste + bloc)
    reste = morceaux.pop()
    for m in morceaux:
        if m.strip():
            sortir(m)
if reste.strip():
    sortir(reste)
'

cd "$JEU" || exit 1
exec stdbuf -oL "$BIN" "${ARGS[@]}" > >(exec python3 -c "$FILTRE")
