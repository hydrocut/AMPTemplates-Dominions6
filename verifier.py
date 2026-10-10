# -*- coding: utf-8 -*-
"""
Contrôle du template avant de le pousser (même rôle que ceux d'Unciv et de Freeciv).

    python verifier.py                 contrôle tout
    python verifier.py --synchroniser  recopie d'abord scripts/lancer-dominions6.sh
                                       dans l'étape CreateFile de dominions6updates.json

Dominions 6 est payant : on ne peut pas lancer le vrai serveur ici. Ce script vérifie donc
tout ce qui peut casser sans le jeu :

1. tous les JSON se parsent ;
2. le .kvp : fichiers inclus, Ref du port, bloc Console.* / Limits.* complet, connexion Steam
   non anonyme, conteneur et paquets ;
3. chaque réglage exposé dans AMP sert (ligne de commande ou condition d'Update), et chaque
   {{Réglage}} utilisé est défini ;
4. la ligne de commande d'AMP : un argument "cle={{Réglage}}" par réglage, et exactement les
   clés que lit le lanceur ;
5. les choix proposés (ère, carte, niveau d'IA, oui/non) sont ceux que le lanceur accepte, et
   chaque option donnée au jeu existe dans le manuel de Dominions 6 (« Launch Options », p. 430-432) ;
6. le lanceur copié dans l'Update est identique à scripts/lancer-dominions6.sh, en LF, ASCII,
   sans {{ ;
7. aller-retour réel (si bash est disponible) : la ligne de commande rendue comme le ferait AMP,
   avec les valeurs par défaut puis des valeurs piégées (espaces, virgules, apostrophe, accents),
   passe par le vrai lanceur, qui doit produire les bons arguments ou refuser proprement ;
8. le filtre de console du lanceur, lancé sur des lignes au format du serveur ;
9. les regex de console sur les lignes que le lanceur écrit.
"""
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
NOM = 'dominions6'
SCRIPT = 'scripts/lancer-dominions6.sh'
soucis = []


def lire(nom, binaire=False):
    chemin = os.path.join(ICI, nom)
    if binaire:
        with open(chemin, 'rb') as f:
            return f.read()
    with io.open(chemin, encoding='utf-8') as f:
        return f.read()


def ok(quoi, detail):
    print('ok   %-26s %s' % (quoi, detail))


def py(motif):
    # AMP est en C# : (?<nom>...) ; Python veut (?P<nom>...)
    return re.compile(motif.replace('(?<', '(?P<'))


# ── 0. synchronisation du lanceur dans l'étape CreateFile ────────────────────
if '--synchroniser' in sys.argv:
    chemin = os.path.join(ICI, NOM + 'updates.json')
    etapes = json.loads(lire(NOM + 'updates.json'))
    for e in etapes:
        if e['UpdateSource'] == 'CreateFile' and e['UpdateSourceArgs'].endswith('lancer-dominions6.sh'):
            e['UpdateSourceData'] = lire(SCRIPT, binaire=True).decode('ascii')
    with io.open(chemin, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(etapes, indent=4, ensure_ascii=False) + '\n')
    print('     lanceur recopié dans %supdates.json' % NOM)

# ── 1. JSON ──────────────────────────────────────────────────────────────────
data = {}
for nom in ('manifest.json', NOM + 'config.json', NOM + 'metaconfig.json', NOM + 'ports.json', NOM + 'updates.json'):
    try:
        data[nom] = json.loads(lire(nom))
        ok(nom, 'JSON valide')
    except Exception as e:
        soucis.append('%s : JSON invalide (%s)' % (nom, e))
if soucis:
    print('\n'.join('NON  ' + s for s in soucis))
    sys.exit(1)
config = data[NOM + 'config.json']
updates = data[NOM + 'updates.json']
ports = data[NOM + 'ports.json']
script = lire(SCRIPT, binaire=True).decode('utf-8')

# ── 2. kvp ───────────────────────────────────────────────────────────────────
kvp = lire(NOM + '.kvp')
cles = dict(l.split('=', 1) for l in kvp.splitlines() if '=' in l)
for ref in re.findall(r'@IncludeJson\[([^\]]+)\]', kvp):
    if not os.path.isfile(os.path.join(ICI, ref)):
        soucis.append('@IncludeJson[%s] : fichier absent' % ref)
for cle in ('Meta.ConfigManifest', 'Meta.MetaConfigManifest'):
    if not os.path.isfile(os.path.join(ICI, cles.get(cle, '?'))):
        soucis.append('%s pointe sur un fichier absent' % cle)
refs = {p['Ref'] for p in ports}
if cles.get('App.PrimaryApplicationPortRef') not in refs:
    soucis.append('PrimaryApplicationPortRef ne correspond à aucun port')
for r in re.findall(r'\{\{\$(\w+)\}\}', cles.get('App.CommandLineArgs', '')):
    if r not in refs and r != 'FullBaseDir':
        soucis.append('{{$%s}} : aucun port ne porte ce Ref' % r)
if any(p['Protocol'] != 'TCP' for p in ports):
    soucis.append('Dominions n’utilise qu’un port TCP (manuel de Dominions 5, « Playing a network game »)')
ok('ports', ', '.join('%s %s/%s' % (p['Ref'], p['Port'], p['Protocol']) for p in ports))
ATTENDUES = ['App.SupportsUniversalSleep', 'App.WakeupMode', 'App.ApplicationReadyMode', 'Console.FilterMatchRegex',
             'Console.FilterMatchReplacement', 'Console.ThrowawayMessageRegex', 'Console.AppReadyRegex',
             'Console.UserJoinRegex', 'Console.UserLeaveRegex', 'Console.UserChatRegex', 'Console.UpdateAvailableRegex',
             'Console.PreConnectRegex', 'Console.ConnectIPRegex', 'Console.MetricsRegex', 'Console.HideFromConsoleRegex',
             'Console.SuppressLogAtStart', 'Console.UserActions', 'Limits.SleepMode', 'Limits.SleepOnStart',
             'Limits.SleepDelayMinutes', 'Limits.DozeDelay', 'Limits.AutoRetryCount', 'Limits.SleepStartThresholdSeconds']
absentes = [c for c in ATTENDUES if c not in cles]
if absentes:
    soucis.append('clés absentes du .kvp : ' + ', '.join(absentes))
else:
    ok('kvp complet', 'les %d clés Console/Limits sont là' % len(ATTENDUES))
if cles.get('App.ApplicationReadyMode') == 'RegexMatch' and not cles.get('Console.AppReadyRegex'):
    soucis.append('RegexMatch sans AppReadyRegex : l’instance ne serait jamais déclarée prête')
ATTENDU_KVP = {
    'App.SteamUpdateAnonymousLogin': 'False',   # jeu payant : compte Steam qui le possède
    'App.SteamForceLoginPrompt': 'True',        # comme Starbound / Stardew Valley chez CubeCoders
    'App.ExitMethod': 'SIGTERM',                # reçu par dom6_amd64 lui-même (exec)
    'App.ExecutableLinux': '/bin/bash',
    'App.MaxUsers': '0',                        # le jeu n'écrit pas qui se connecte
    'Meta.ContainerPolicy': 'Required',
    'Meta.DisplayImageSource': 'steam:2511500',
}
for cle, val in ATTENDU_KVP.items():
    if cles.get(cle) != val:
        soucis.append('%s devrait valoir %s (vaut %r)' % (cle, val, cles.get(cle)))
paquets = json.loads(cles.get('Meta.ExtraContainerPackages', '[]'))
for p in ('libsdl2-2.0-0', 'libgl1', 'libglu1-mesa', 'python3'):
    if p not in paquets:
        soucis.append('ExtraContainerPackages : %s manque' % p)
ok('kvp', 'Steam non anonyme, SIGTERM, conteneur + %d paquets' % len(paquets))

# ── 3. réglages utilisés <-> définis ─────────────────────────────────────────
definis = [c['FieldName'] for c in config]
if len(definis) != len(set(definis)):
    soucis.append('réglages en double')
cmd = cles['App.CommandLineArgs']
dans_cmd = set(re.findall(r'\{\{([A-Za-z]\w*)\}\}', cmd))
dans_update = set(re.findall(r'\{\{([A-Za-z]\w*)\}\}', json.dumps(updates)))
conditions = {e['UpdateSourceConditionSetting'] for e in updates if e.get('UpdateSourceConditionSetting')}
utilises = dans_cmd | dans_update | conditions
for u in sorted(utilises - set(definis)):
    soucis.append('{{%s}} utilisé mais défini nulle part dans %sconfig.json' % (u, NOM))
for d in sorted(set(definis) - utilises):
    soucis.append('réglage %s exposé dans AMP mais utilisé nulle part' % d)
if not (utilises ^ set(definis)):
    ok('réglages', '%d définis : %d en ligne de commande, %d en condition d’Update'
       % (len(definis), len(dans_cmd), len(conditions)))
par_nom = {c['FieldName']: c for c in config}
for c in config:
    ev, d = c.get('EnumValues') or {}, c.get('DefaultValue')
    if c['InputType'] == 'enum' and d not in ev:
        soucis.append('%s : DefaultValue %r absente de la liste' % (c['FieldName'], d))
    if c['InputType'] == 'checkbox' and d not in ev.values():
        soucis.append('%s : DefaultValue %r absente des valeurs de la case' % (c['FieldName'], d))

# ── 4. ligne de commande <-> lanceur ─────────────────────────────────────────
morceaux = shlex.split(cmd)
if morceaux[0] != '{{$FullBaseDir}}lancer-dominions6.sh':
    soucis.append('la ligne de commande doit commencer par le lanceur')
cles_cmd = {}
for m in morceaux[1:]:
    r = re.fullmatch(r'([a-z]+)=\{\{\$?(\w+)\}\}', m)
    if not r:
        soucis.append('argument %r : attendu cle={{Réglage}}, entre guillemets' % m)
        continue
    cles_cmd[r.group(1)] = r.group(2)
for brut in re.findall(r'"[^"]*"|\S+', cmd)[1:]:
    if not (brut.startswith('"') and brut.endswith('"')):
        soucis.append('argument %s sans guillemets : une espace dans la valeur le couperait en deux' % brut)
lues = set(re.findall(r'\$\{V\[(\w+)\]', script))
if set(cles_cmd) != lues:
    soucis.append('clés passées par AMP %s ≠ clés lues par le lanceur %s' % (sorted(cles_cmd), sorted(lues)))
else:
    ok('ligne de commande', '%d arguments cle=valeur, tous lus par le lanceur' % len(cles_cmd))

# ── 5. choix proposés <-> lanceur <-> manuel ─────────────────────────────────
def accepte(variable):
    m = re.search(r'\[\[ "\$%s" =~ \^\(?([^$)]*)\)?\$ \]\]' % variable, script)
    if not m:
        return None
    motif = m.group(1)
    if motif.startswith('['):
        return set(motif.strip('[]'))
    return set(motif.split('|'))


for champ, variable in (('Ere', 'ERE'), ('Carte', 'CARTE'), ('NiveauIA', 'NIVEAU')):
    permis = accepte(variable)
    choix = set(par_nom[champ]['EnumValues'])
    if permis is None:
        soucis.append('contrôle de %s introuvable dans le lanceur' % variable)
    elif choix != permis:
        soucis.append('%s : AMP propose %s, le lanceur accepte %s' % (champ, sorted(choix), sorted(permis)))
    else:
        ok('choix ' + champ, ', '.join(sorted(choix)))
if set(par_nom['ClientsLancent']['EnumValues'].values()) != accepte('CLIENTS'):
    soucis.append('ClientsLancent : la case doit donner oui/non, comme l’attend le lanceur')

# Options relevées dans le manuel officiel (dom6manual.pdf, « Launch Options », p. 430-432).
MANUEL = {'--tcpserver', '--textonly', '--nosteam', '--statusdump', '--port', '--minutes', '--hours',
          '--noclientstart', '--era', '--mapfile', '--randmap', '--uploadmaxp', '--uploadtime',
          '--easyai', '--normai', '--diffai', '--mightyai', '--masterai', '--impai', '--masterpass',
          '--research', '--renaming', '--thrones', '--version'}
donnees = set(re.findall(r'(--[a-z]+)', ' '.join(re.findall(r'ARGS(?:\+)?=\((.*)\)', script))))
donnees |= {'--%sai' % n for n in par_nom['NiveauIA']['EnumValues']}
inconnues = donnees - MANUEL
if inconnues:
    soucis.append('options absentes du manuel de Dominions 6 : %s' % ', '.join(sorted(inconnues)))
else:
    ok('options du jeu', '%d options, toutes dans le manuel' % len(donnees))

# ── 6. lanceur dans l'Update ─────────────────────────────────────────────────
brut = lire(SCRIPT, binaire=True)
if b'\r' in brut:
    soucis.append('%s : fins de ligne Windows (CRLF), bash refusera' % SCRIPT)
if any(o > 127 for o in brut):
    soucis.append('%s : caractères non ASCII' % SCRIPT)
if '{{' in script:
    soucis.append('%s contient {{ : AMP pourrait le remplacer' % SCRIPT)
if not script.startswith('#!/bin/bash\n'):
    soucis.append('%s : doit commencer par #!/bin/bash' % SCRIPT)
cf = [e for e in updates if e['UpdateSource'] == 'CreateFile']
if len(cf) != 1 or cf[0]['UpdateSourceArgs'] != '{{$FullBaseDir}}lancer-dominions6.sh':
    soucis.append('une seule étape CreateFile attendue, vers {{$FullBaseDir}}lancer-dominions6.sh')
elif cf[0]['UpdateSourceData'] != script:
    soucis.append('le lanceur de l’Update diffère de %s : lancer python verifier.py --synchroniser' % SCRIPT)
elif cf[0].get('OverwriteExistingFiles') is not True:
    soucis.append('le lanceur doit être réécrit à chaque Update (OverwriteExistingFiles true)')
else:
    ok('lanceur', 'identique dans l’Update, LF, ASCII, sans {{')
st = [e for e in updates if e['UpdateSource'] == 'SteamCMD']
if (len(st) != 1 or st[0]['UpdateSourceData'] != '2511500' or st[0].get('UpdateSourceConditionSetting') != 'SourceJeu'
        or st[0].get('UpdateSourceConditionValue') not in par_nom['SourceJeu']['EnumValues']
        or st[0].get('UpdateSourceTarget') != '{{$FullBaseDir}}jeu'):
    soucis.append('étape SteamCMD : app 2511500, vers {{$FullBaseDir}}jeu, seulement si SourceJeu=steamcmd')
elif 'JEU="$ICI/jeu"' not in script:
    soucis.append('le lanceur ne cherche pas le jeu dans jeu/, là où SteamCMD l’installe')
else:
    ok('SteamCMD', 'app 2511500 -> jeu/, si SourceJeu = steamcmd')
if not any(e['UpdateSource'] == 'Executable' and e['UpdateSourceArgs'].endswith('lancer-dominions6.sh" verifier')
           and e.get('SkipOnFailure') is True for e in updates):
    soucis.append('il manque l’étape de vérification (lancer-dominions6.sh verifier, SkipOnFailure true)')


# ── 7. aller-retour réel par le lanceur ──────────────────────────────────────
def trouver_bash():
    for c in (r'C:\Program Files\Git\bin\bash.exe', r'C:\Program Files\Git\usr\bin\bash.exe', '/bin/bash'):
        if os.path.isfile(c):
            return c
    c = shutil.which('bash')
    if c and 'system32' not in c.lower():   # le bash de WSL ne verrait pas les chemins Windows
        return c
    return None


DEFAUTS = {c['FieldName']: c.get('DefaultValue', '') for c in config}
PORT = str(ports[0]['Port'])


def lancer(bash, dossier, valeurs):
    ligne = cmd.replace('{{$FullBaseDir}}', dossier.replace('\\', '/') + '/').replace('{{$GamePort}}', PORT)
    for k, v in valeurs.items():
        ligne = ligne.replace('{{%s}}' % k, v)
    argv = shlex.split(ligne)
    sortie_args = os.path.join(dossier, 'args.txt')
    if os.path.exists(sortie_args):
        os.remove(sortie_args)
    env = dict(os.environ, TK_ESSAI_ARGS=sortie_args.replace('\\', '/'))
    p = subprocess.run([bash] + argv, env=env, capture_output=True, timeout=60)
    texte = p.stdout.decode('utf-8', 'replace') + p.stderr.decode('utf-8', 'replace')
    args = None
    if os.path.exists(sortie_args):
        with io.open(sortie_args, encoding='utf-8') as f:
            args = f.read().split('\n')[:-1]
    return p.returncode, texte, args


BASE = ['--tcpserver', '--textonly', '--nosteam', '--statusdump', '--port', PORT]
bash = trouver_bash()
if not bash:
    print('---  aller-retour          bash introuvable : étape 7 sautée (à faire avant de pousser)')
else:
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(ICI, SCRIPT), os.path.join(tmp, 'lancer-dominions6.sh'))
        os.makedirs(os.path.join(tmp, 'jeu'))
        with open(os.path.join(tmp, 'jeu', 'dom6_amd64'), 'w') as f:
            f.write('faux binaire\n')
        CAS = [
            ('valeurs par défaut', {}, 0,
             BASE + ['--minutes', '1440', '--era', '2', '--randmap', '15', 'TeamKit_FR']),
            ('valeurs piégées', {'Carte': 'fichier', 'FichierCarte': "Carte, la grande d'été.map",
                                 'NationsIA': '50, 60 71', 'NiveauIA': 'diff', 'ClientsLancent': 'non',
                                 'JoueursAttendus': '4', 'DelaiDemarrage': '48', 'DelaiTour': '0',
                                 'MotDePasseMaitre': 'Secret_1', 'OptionsEnPlus': '--research 3  --renaming',
                                 'Ere': '3'}, 0,
             BASE + ['--noclientstart', '--era', '3', '--mapfile', "Carte, la grande d'été.map",
                     '--uploadmaxp', '4', '--uploadtime', '2880', '--diffai', '50', '--diffai', '60',
                     '--diffai', '71', '--masterpass', 'Secret_1', '--research', '3', '--renaming', 'TeamKit_FR']),
            ('nom avec une espace', {'NomPartie': 'Ma partie'}, 1, None),
            ('nom avec un accent', {'NomPartie': 'Partie_été'}, 1, None),
            ('nom vide', {'NomPartie': ''}, 1, None),
            ('mot de passe avec espace', {'MotDePasseMaitre': 'mot de passe'}, 1, None),
            ('mot de passe avec virgule', {'MotDePasseMaitre': 'a,b'}, 1, None),
            ('nation IA invalide', {'NationsIA': '50 abc'}, 1, None),
            ('nation IA hors bornes', {'NationsIA': '600'}, 1, None),
            ('carte fichier sans nom', {'Carte': 'fichier'}, 1, None),
            ('carte avec chemin', {'Carte': 'fichier', 'FichierCarte': '../secret.map'}, 1, None),
        ]
        for titre, change, code_attendu, attendu in CAS:
            valeurs = dict(DEFAUTS, **change)
            code, texte, args = lancer(bash, tmp, valeurs)
            if code != code_attendu:
                soucis.append('aller-retour « %s » : code %s au lieu de %s\n%s' % (titre, code, code_attendu, texte))
            elif attendu is not None and args != attendu:
                soucis.append('aller-retour « %s » :\n       obtenu  %s\n       attendu %s' % (titre, args, attendu))
            elif code == 1 and ('ERREUR' not in texte or args is not None):
                soucis.append('aller-retour « %s » : refus sans message clair, ou jeu lancé quand même' % titre)
            elif 'Secret_1' in texte:
                soucis.append('aller-retour « %s » : le mot de passe maître apparaît dans la console' % titre)
        # reprise : la sauvegarde existe, les réglages de création ne sont plus passés
        os.makedirs(os.path.join(tmp, 'donnees', 'savedgames', 'TeamKit_FR'))
        open(os.path.join(tmp, 'donnees', 'savedgames', 'TeamKit_FR', 'ftherlnd'), 'w').close()
        code, texte, args = lancer(bash, tmp, dict(DEFAUTS, MotDePasseMaitre='Secret_1', NationsIA='50'))
        if code != 0 or args != BASE + ['--minutes', '1440', 'TeamKit_FR'] or 'reprise de la partie' not in texte:
            soucis.append('aller-retour « reprise » : %s %s' % (code, args))
        if not [s for s in soucis if s.startswith('aller-retour')]:
            ok('aller-retour', '%d cas par le vrai lanceur (bash), reprise comprise' % (len(CAS) + 1))
        # mode verifier sans les fichiers du jeu : message clair, code 1
        os.remove(os.path.join(tmp, 'jeu', 'dom6_amd64'))
        p = subprocess.run([bash, os.path.join(tmp, 'lancer-dominions6.sh').replace('\\', '/'), 'verifier'],
                           capture_output=True, timeout=60)
        if p.returncode != 1 or b'absents' not in p.stdout:
            soucis.append('lancer-dominions6.sh verifier sans le jeu : message ou code inattendu')

# ── 8. filtre de console du lanceur ──────────────────────────────────────────
m = re.search(r"^FILTRE='\n(.*?)^'$", script, re.S | re.M)
if not m:
    soucis.append('programme FILTRE introuvable dans le lanceur')
else:
    # Formats relevés par MrClockwork-v4 (games/dominions_runtime_data_handler.js) sur le serveur
    # Dominions 5 ; le compte à rebours « N seconds » vient des motifs ignorés par yggdrasil (Dominions 6).
    ENTREE = (b'sh: 1: kdialog: not found\n'
              b'Setup port 6090 (clients may start), 30 seconds, open: 37, players 0, ais 0\r'
              b'Setup port 6090 (clients may start), 29 seconds, open: 37, players 0, ais 0\r\n'
              b'Setup port 6090 (clients may start), 28 seconds, open: 37, players 1, ais 0\n'
              b'TeamKit_FR, Connections 1, No timer (quick host)\n(Arc) (Ul) Va+ Rus? *La-\n'
              b'TeamKit_FR, Connections 1, No timer (quick host)\n(Arc) (Ul) Va+ Rus? *La-\n'
              b'TeamKit_FR, Connections 2, No timer (quick host)\n(Arc) Ul+ Va+ Rus? *La-\n'
              b'Pyr\xe8ne\nGenerating next turn\n')
    ATTENDU = ['sh: 1: kdialog: not found',
               'Setup port 6090 (clients may start), 30 seconds, open: 37, players 0, ais 0',
               'Setup port 6090 (clients may start), 28 seconds, open: 37, players 1, ais 0',
               'TeamKit_FR, Connections 1, No timer (quick host)', '(Arc) (Ul) Va+ Rus? *La-',
               'TeamKit_FR, Connections 2, No timer (quick host)', '(Arc) Ul+ Va+ Rus? *La-',
               'Pyrène', 'Generating next turn']
    p = subprocess.run([sys.executable, '-c', m.group(1)], input=ENTREE, capture_output=True, timeout=30)
    obtenu = p.stdout.decode('utf-8').split('\n')[:-1]
    if obtenu != ATTENDU:
        soucis.append('filtre de console :\n       obtenu  %s\n       attendu %s\n%s' % (obtenu, ATTENDU, p.stderr.decode()))
    else:
        ok('filtre de console', '%d lignes reçues, %d gardées (doublons et compte à rebours retirés)'
           % (ENTREE.count(b'\n') + ENTREE.count(b'\r') - ENTREE.count(b'\r\n'), len(ATTENDU)))

# ── 9. regex de console ──────────────────────────────────────────────────────
echo = re.search(r'echo "(TeamKit : Dominions 6 ecoute sur le port \$PORT \(partie \$NOM\)\.)"', script)
if not echo:
    soucis.append('ligne « prêt » introuvable dans le lanceur')
else:
    pret = echo.group(1).replace('$PORT', PORT)
    ESSAIS = [
        ('Console.AppReadyRegex', pret.replace('$NOM', 'TeamKit_FR'), True),
        ('Console.AppReadyRegex', pret.replace('$NOM', 'Partie-2'), True),
        ('Console.AppReadyRegex', 'TeamKit : ATTENTION, le port 6090 n\'est toujours pas ouvert apres 3 minutes.', False),
        ('Console.AppReadyRegex', 'Setup port 6090 (clients may start), 30 seconds, open: 37, players 0, ais 0', False),
        ('Console.AppReadyRegex', 'TeamKit : reprise de la partie TeamKit_FR (dossier donnees/savedgames/TeamKit_FR).', False),
        ('Console.ThrowawayMessageRegex', 'sh: 1: kdialog: not found', True),
        ('Console.ThrowawayMessageRegex', 'sh: 1: zenity: not found', True),
        ('Console.ThrowawayMessageRegex', pret.replace('$NOM', 'TeamKit_FR'), False),
        ('Console.ThrowawayMessageRegex', 'Map specified by --mapfile was not found', False),
        ('Console.ThrowawayMessageRegex', 'Generating next turn', False),
    ]
    for cle, ligne, attendu in ESSAIS:
        if bool(py(cles[cle]).search(ligne)) != attendu:
            soucis.append('%s %s : %s' % (cle, 'devrait reconnaître' if attendu else 'ne devrait pas reconnaître', ligne))
    ok('console', '%d lignes testées (prêt, bruit)' % len(ESSAIS))

print()
if soucis:
    print('%d problème(s) :' % len(soucis))
    print('\n'.join('  NON  ' + s for s in soucis))
    sys.exit(1)
print('Tout est bon.')
