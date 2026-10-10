# AMPTemplates-Dominions6 — Dominions 6 multiplayer server for AMP

**AMP Generic Module** template to host a **Dominions 6 – Rise of the Pantokrator** network game
(Illwinter Game Design, 2024) on Linux. Written for TeamKit, a free French game host, on 10 Oct. 2026.
CubeCoders ships no Dominions template.

> Résumé en français à la fin du fichier.

**Dominions 6 is a paid game** (Steam app `2511500`). This repository contains **no game file** and
downloads none by itself: the files come from a Steam account that owns the game, or are copied by
hand from an existing Steam install. Every player also needs their own copy of the game.

> **Status: not run against the real game yet.** Everything below comes from Illwinter's manuals,
> Steam's app data and community hosting tools (sources at the end); the launcher was tested with a
> stand-in binary. See *What must be checked on first start*.

## What the server is

There is no separate server program: the game itself runs headless as the server
(`dom6_amd64 --tcpserver --textonly`). Turns are **simultaneous**: players connect when they want,
download their turn, give orders and send them back; the server generates the next turn when
everyone is done, or when the turn timer runs out. A game commonly lasts weeks at one turn a day.

- **One TCP port** (6090 by default, chosen by TeamKit: Dominions has no default port). The
  Dominions 5 manual: "Only the port chosen in the Setup Dominions server screen needs to be
  forwarded — nothing else."
- **No player list in AMP** (`App.MaxUsers=0`): the server does not print who connects.
- **Server and clients must run the same game version** (Dominions 5 manual, "Playing a network
  game"). Steam updates players automatically, so update the server after each Dominions patch.

## Getting the game files

| Source (setting *Source des fichiers du jeu*) | How | For / against |
|---|---|---|
| **SteamCMD (default, recommended)** | the Update stage `SteamCMD` downloads app `2511500` into `jeu/` with a Steam account that owns the game (`App.SteamUpdateAnonymousLogin=False`, `App.SteamForceLoginPrompt=True`, as in CubeCoders' Starbound and Stardew Valley templates) | stays on the players' version with one click; but AMP keeps a SteamCMD login for that account on the server |
| **Manual** | copy the content of `steamapps/common/Dominions6` from a PC into `dominions6/jeu/` (SFTP or AMP file manager), then Update | no Steam login on the server; but redo it after every game patch |

Why the manual copy works from a **Windows** PC: Steam's app data has a single depot (`2511501`,
721 MB) with no OS restriction, launched as `Dominions6.exe` on Windows and `dom6.sh` on Linux,
so every install holds `dom6_amd64` too (also relied on by blitzserver and Dom6-Mod-Editor).
Illwinter sells Dominions 6 **only on Steam** ("Dominions 6 can be bought on Steam", illwinter.com/dom6):
there is no DRM-free Linux archive to buy, unlike older Dominions.

**Steam Guard:** on the first SteamCMD login, approve it in the Steam mobile app (shield icon →
approve). Reported on the CubeCoders forum, thread 42461, AMP 2.8.0.4: waiting for the approval
times out if nobody approves.

### The CD key (`dom6key`)

Dominions 6 is protected by a CD key, not by Steam DRM. Steam's app data declares a legacy key
written to disk as **`dom6key`** in the install folder. It is not known whether the headless server
needs it, nor whether SteamCMD writes it. If the server refuses to start or asks for a key, copy
`dom6key` from the PC's install folder into `dominions6/jeu/`. **It is a secret**: never commit or
share it (`.gitignore` excludes it). The update check stage tells whether it is present.

## Files

| File | Role |
|---|---|
| `dominions6.kvp`, `dominions6*.json`, `manifest.json` | the AMP template |
| `scripts/lancer-dominions6.sh` | launcher, written to the instance by the `CreateFile` Update stage (no download from this repository) |
| `verifier.py` | pre-push checks, must print `Tout est bon.` |

Instance layout: `dominions6/jeu/` = game files, `dominions6/donnees/` = Dominions' user folder
(`savedgames/`, `maps/`, `mods/`), `dominions6/lancer-dominions6.sh`.

## Update stages

1. create `jeu/`;
2. **SteamCMD** app `2511500` → `jeu/`, only when *Source* = SteamCMD;
3. **CreateFile** `lancer-dominions6.sh` (rewritten at each Update, so fixes reach existing
   instances);
4. **check** (`lancer-dominions6.sh verifier`, `SkipOnFailure`): game present, `ldd` finds every
   library, `--version`, `dom6key` present or not, and `--listnations` saved to `donnees/nations.txt`.

Container: `cubecoders/ampbase:debian` (Debian 13), **required**. `ExtraContainerPackages` adds
`libsdl2-2.0-0`, `libgl1`, `libglu1-mesa` (the binary needs them even headless, per the community
tools) and `python3` (console filter). Checked on 10 Oct. 2026 in a throwaway container: SDL2 and
libGL are already in the image, **GLU is not**, `libglu1-mesa` exists in Debian 13; `python3`,
`stdbuf`, `xvfb-run` are present.

## How the server is started

AMP runs `/bin/bash lancer-dominions6.sh "port=…" "nom=…" "ere=…" …`: one quoted `key=value`
argument per setting, so an empty setting stays an argument (`"ia="`) and never shifts the others.
The launcher checks every value, then runs, from `jeu/`:

```
dom6_amd64 --tcpserver --textonly --nosteam --statusdump --port 6090 [--minutes N] [--noclientstart]
           # new game only:
           --era 2 (--randmap 15 | --mapfile X.map) [--uploadmaxp N] [--uploadtime MIN]
           [--normai 50 --normai 60 …] [--masterpass X]
           [extra options] <game name>
```

- `DOM6_CONF`, `DOM6_SAVE`, `DOM6_LOCALMAPS`, `DOM6_MODS` point into `donnees/` (names found in the
  binary by the dom6-arm project; `DOM6_CONF` is what yggdrasil and blitzserver set). Without them
  the game would write to `~/.dominions6`.
- **Resume:** if `donnees/savedgames/<name>/ftherlnd` exists the game has been created, so only
  server options are passed; era, map, AI and master password are fixed in the save.
- `--nosteam` ("workshop will be unavailable"), as Hosting-slave-v4 does: no Steam client runs in
  the container.
- `exec stdbuf -oL dom6_amd64 …`: the game is the process AMP signals (`App.ExitMethod=SIGTERM`,
  checked with a stand-in binary), its output is line-buffered.
- Its stdout goes through a small Python filter: the server prints a status line **every second**
  (`Setup port 6090 (clients may start), open: 35, players 0, ais 0`,
  `<game>, Connections 1, No timer (quick host)`, and a nation line such as `(Arc) (Ul) Va+ Rus? *La-`;
  formats recorded by MrClockwork-v4 on Dominions 5). The filter only lets such a line through when
  it changed (countdowns ignored), splits on lone `\r`, and converts Latin-1 to UTF-8. Every other
  line passes unchanged.
- **Ready line** (`Console.AppReadyRegex`): written by the launcher itself once the TCP port is
  actually listening (read in `/proc/net/tcp*`), so it does not depend on the game's wording:
  `TeamKit : Dominions 6 ecoute sur le port 6090 (partie TeamKit_FR).`

### Why values are restricted

AMP writes each value as is into the command line. The launcher therefore accepts, for the game
name and the master password, only `A-Z a-z 0-9 _ -` (no space, quote or accent) and refuses to
start otherwise, with a French message in the console. The map file name may contain spaces,
commas, apostrophes and accents (tested), but not `"`. The AI nation list is split on spaces and
commas on purpose. Extra options are split on spaces.

## Settings (French UI)

| Setting | Game option | Default |
|---|---|---|
| Port du jeu (Network tab) | `--port` | 6090/TCP |
| Source des fichiers du jeu | Update stage | SteamCMD |
| Nom de la partie | game name (folder `donnees/savedgames/<name>`) | `TeamKit_FR` |
| Ère | `--era 1-3` | 2 (Middle Age) |
| Carte / Fichier de la carte | `--randmap 10/15/20` or `--mapfile` | random, 15 provinces per player |
| Délai maximum d'un tour | `--minutes` (none = wait for everyone) | 24 h |
| Les joueurs peuvent lancer la partie | `--noclientstart` when unchecked | checked (game default) |
| Démarrer dès que N joueurs… | `--uploadmaxp` | 0 (off) |
| Démarrer au plus tard après (heures) | `--uploadtime` (minutes) | 0 (off) |
| Nations jouées par l'IA + Niveau | `--easyai` … `--impai` | none, normal |
| Mot de passe maître | `--masterpass` | empty |
| Options du jeu en plus | any *Launch Options* | empty |

All options are from the Dominions 6 manual, *Launch Options*, pages 430-432. Dominions has no
message-of-the-day option: the game name is the only text players see.

### AI nation numbers

Each era has its own numbers. `donnees/nations.txt` (written at Update) is the authoritative list
for the installed version. Community list (MrClockwork-v4 `json/dom6_nations.json`), for reference:

- **Early (1):** 5 Arcoscephale, 6 Mekone, 7 Pangaea, 8 Ermor, 9 Sauromatia, 10 Fomoria, 11 Tir na n'Og, 12 Marverni, 13 Ulm, 14 Pyrène, 15 Agartha, 16 Abysia, 17 Hinnom, 18 Ubar, 19 Ur, 20 Kailasa, 21 Lanka, 22 T'ien Ch'i, 23 Yomi, 24 Caelum, 25 Mictlan, 26 Xibalba, 27 C'tis, 28 Machaka, 29 Berytos, 30 Vanheim, 31 Helheim, 32 Rus, 33 Niefelheim, 34 Muspelheim, 40 Pelagia, 41 Oceania, 42 Therodos, 43 Atlantis, 44 R'lyeh
- **Middle (2):** 50 Arcoscephale, 51 Phlegra, 52 Pangaea, 53 Asphodel, 54 Ermor, 55 Sceleria, 56 Pythium, 57 Man, 58 Eriu, 59 Agartha, 60 Ulm, 61 Marignon, 62 Pyrène, 63 Abysia, 64 Ashdod, 65 Na'Ba, 66 Uruk, 67 Ind, 68 Bandar Log, 69 T'ien Ch'i, 70 Shinuyama, 71 Caelum, 72 Nazca, 73 Mictlan, 74 Xibalba, 75 C'tis, 76 Machaka, 77 Phaeacia, 78 Vanheim, 79 Vanarus, 80 Jotunheim, 81 Nidavangr, 85 Ys, 86 Pelagia, 87 Oceania, 88 Atlantis, 89 R'lyeh
- **Late (3):** 95 Arcoscephale, 96 Phlegra, 97 Pangaea, 98 Pythium, 99 Lemuria, 100 Man, 101 Ulm, 102 Agartha, 103 Marignon, 104 Abysia, 105 Ragha, 106 Caelum, 107 Gath, 108 Patala, 109 T'ien Ch'i, 110 Jomon, 111 Mictlan, 112 Xibalba, 113 C'tis, 115 Midgard, 116 Bogarus, 117 Utgard, 118 Vaettiheim, 119 Feminie, 120 Piconye, 121 Andramania, 123 Pyrène, 124 Zemaitia, 125 Erytheia, 126 Atlantis, 127 R'lyeh

## How players join and play

1. Before joining: create a pretender god in *Tools & Manuals → Create a Pretender God* and
   **give it a password** (otherwise anyone can look at or change your turns — Dominions 6 manual).
2. *Network → Connect to a Game Server*, type the server IP, OK, then the port, OK
   (wording from the community guide on illwiki).
3. In the nation list, click *Open* next to a nation to claim it, then load your pretender
   (Dominions 5 manual).
4. The game is created when a player starts it (if allowed), when *N* players have joined
   (`--uploadmaxp`), when the start delay ends (`--uploadtime`), or by hand (below).
5. Each turn: connect, play, end the turn (orders are uploaded). The next turn is generated when
   everyone has played (quick host, the default) or at the end of the turn delay; a player who did
   not play keeps their position with no new orders ("stale turn").

`donnees/savedgames/<name>/statusdump.txt` (`--statusdump`) always shows the turn and who has
played; yggdrasil documents its tab-separated format. A future Discord reminder can read it.

### Controlling a running game (`domcmd`)

Dominions reads a file named `domcmd` in the game folder, then deletes it (Dominions 5 technical
manual; yggdrasil uses `settimeleft` with Dominions 6). With the AMP file manager, create
`donnees/savedgames/<name>/domcmd` containing one command per line, written in one go:

| Command | Effect |
|---|---|
| `settimeleft 5` | next turn (or game creation, during the nation choice) in 5 seconds |
| `setinterval 2880` | turn delay set to 48 h |
| `setquickhost 0` / `1` | do not / do host as soon as everyone has played |
| `setpause <day 0-6> <0/1>` | pause the timer on that weekday (0 = Sunday) |

## Resources

| | |
|---|---|
| Disk | 721 MB of game files (Steam depot size) + saves |
| RAM | **estimate, not measured**: a few hundred MB idle; turn generation with many AI nations on a large map uses more. Plan 1 GB, 2 GB for big games. Steam lists 4 GB for the client with graphics |
| CPU | idle between turns; a burst at each turn generation |

## What must be checked on first start

Nothing below could be tested without the game (paid; nothing paid or pirated was downloaded):

1. SteamCMD login with Steam Guard from AMP, and the download of app 2511500 to `jeu/`.
2. The check stage: `ldd` finds every library (else add the missing package), `--version` works.
3. Whether the server needs `dom6key`, and whether a key shared with a player causes a
   "CD key violation" on this server.
4. The real console lines (the filter only removes repeats; worst case the console is noisy).
5. The ready line appears (port listening), then a client connects with IP + port.
6. Resume after Stop / Start, in the nation choice and during the game, and whether `--minutes`
   given at resume overrides the delay stored in the save.
7. Effect of SIGTERM (stop between turns, never during "Generating next turn").
8. Whether `App.SteamForceLoginPrompt=True` asks for a Steam login even with *Source = manual*.
9. That AMP backups contain `donnees/savedgames/`.

## Before pushing

```
python verifier.py                 # must print "Tout est bon."
python verifier.py --synchroniser  # after editing scripts/lancer-dominions6.sh
```

It checks the JSON, the port `Ref`, that every setting is used and every `{{Setting}}` defined, that
AMP's arguments are exactly the keys the launcher reads, that the offered choices are the ones the
launcher accepts and every game option exists in the manual, that the launcher embedded in the
Update is identical to `scripts/`, then runs the **real launcher** through bash on default and
tricky values (spaces, commas, apostrophe, accents, bad names and passwords, resume), runs the
console filter on sample lines and tests the console regexes.

## Sources

- illwinter.com/dom6 — bought on Steam only, Steam app 2511500.
- *Dominions 6 Manual* (dom6manual.pdf, revision 2): *Launch Options* p. 430-432; *Playing a network
  game* p. 18 (private servers: see the Dominions 5 manual); *Master password* p. 16; game folders p. 14.
- *Dominions 5 Manual* (dom5manual.pdf), *Playing a network game* p. 19-20: one port, same versions.
- illwinter.com/dom5/techmanual.html: `DOM5_CONF`/`DOM5_SAVE` variables, `domcmd` commands.
- Steam store API (`appdetails?appids=2511500`): Linux supported, 43.99 €; api.steamcmd.net
  (`/v1/info/2511500`): depot 2511501 (721 MB, no OS list), Linux launch `dom6.sh`, `legacykeydisklocation dom6key`.
- Community hosting tools: JTorKag/yggdrasil `nidhogg.py` and README (command line, `DOM6_CONF`,
  packages, `domcmd`, `statusdump.txt`); blitzserver (`DOM6_CONF`, zip of the Steam folder,
  `--version` output); Drithyl/Hosting-slave-v4 `dominions/game.js` (`--nosteam --statusdump
  --textonly`); Drithyl/MrClockwork-v4 `games/dominions_runtime_data_handler.js` (console lines);
  mholovaty/dom6-arm `src/loader_main.c` (`DOM6_*` variables); illwiki *Join multiplayer game guide*;
  Steam discussion "CD Key violation?" (7 Mar 2024).
- CubeCoders AMPTemplates: `starbound.kvp`, `stardew-valley.kvp` (Steam login), `UpdateSourceConditionSetting`.

## Credits

Dominions 6 is © Illwinter Game Design. This repository only contains the template; it ships no
game file and no key.

---

## Résumé en français

Template AMP pour un **serveur multijoueur Dominions 6** (Illwinter, **jeu payant**, Steam 2511500).
Le serveur, c'est le jeu lui-même lancé sans affichage. Tours simultanés, un délai par tour réglable :
pensé pour une partie communautaire sur plusieurs semaines.

- **Fichiers du jeu** : par SteamCMD avec un compte Steam qui possède le jeu (par défaut, validation
  Steam Guard dans l'appli mobile la première fois), ou copiés à la main depuis le dossier Steam d'un
  PC (même Windows : il contient aussi la version Linux). Le jeu n'est vendu que sur Steam.
- **Un seul port TCP** (6090). **Pas de liste de joueurs** dans AMP (le jeu n'écrit pas qui se connecte).
- **Réglages en français** : nom de la partie, ère, carte, délai des tours, démarrage, IA, mot de passe
  maître, options en plus. Le nom et le mot de passe maître : lettres sans accent, chiffres, _ et -
  seulement (le serveur refuse de démarrer sinon et le dit).
- **Se connecter** : Network → Connect to a Game Server → IP puis port → choisir une nation → charger
  son dieu (protégé par un mot de passe).
- **Pas encore lancé avec le vrai jeu** : la liste de ce qu'il faut vérifier au premier démarrage est
  plus haut (clé CD `dom6key`, Steam Guard, lignes de la console, reprise).
- Avant de pousser : `python verifier.py` doit répondre « Tout est bon. ».
