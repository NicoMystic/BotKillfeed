import re
import os
import json
import glob
import paramiko
from datetime import datetime

# Paramètres de connexion SFTP
SFTP_HOST = '193.25.252.91'
SFTP_PORT = 8822
SFTP_USERNAME = 'nicolasd'
SFTP_PASSWORD = '57!9d1QemdSOD['
DAYZ_LOG_FILE_PATH = '/193.25.252.91_2330/ServerProfile/DayZServer_x64.ADM'


def retrieve_dayz_log_sftp():
    try:
        transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
        transport.connect(username=SFTP_USERNAME, password=SFTP_PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)

        local_path = 'DayZServer_x64.ADM'
        possible_paths = [
            DAYZ_LOG_FILE_PATH,
            '/193.25.252.91_2330/DayZServer_x64.ADM',
            '/home/nicolasd/193.25.252.91_2330/ServerProfile/DayZServer_x64.ADM'
        ]

        success = False
        for path in possible_paths:
            try:
                sftp.get(path, local_path)
                success = True
                print(f"Fichier récupéré avec succès depuis {path}")
                break
            except Exception as e:
                print(f"Échec de récupération depuis {path}: {e}")

        sftp.close()
        transport.close()

        if success:
            print(f"Fichier de log récupéré avec succès depuis {SFTP_HOST}.")
            return local_path
        else:
            print("Impossible de récupérer le fichier de log via SFTP.")
            return None
    except Exception as e:
        print(f"Erreur lors de la récupération du fichier SFTP : {e}")
        return None


def retrieve_all_source_logs():
    try:
        transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
        transport.connect(username=SFTP_USERNAME, password=SFTP_PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)

        remote_dir = '/193.25.252.91_2330/ServerProfile'
        files = sftp.listdir(remote_dir)

        for file in files:
            if file.startswith("Mystic_SourceLogs_") and file.endswith(".ljson"):
                remote_path = f"{remote_dir}/{file}"
                local_path = file
                sftp.get(remote_path, local_path)
                print(f"[OK] Téléchargé : {file}")

        sftp.close()
        transport.close()
    except Exception as e:
        print(f"[ERREUR] Échec récupération des fichiers .ljson : {e}")


def parse_dayz_log(custom_file=None):
    events = []

    retrieve_all_source_logs()
    log_file_path = custom_file or retrieve_dayz_log_sftp()
    if not log_file_path and os.path.exists("DayZServer_x64.ADM"):
        log_file_path = "DayZServer_x64.ADM"
        print("Utilisation du fichier local existant")

    if log_file_path and os.path.exists(log_file_path):
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
                lines = file.readlines()

                connect_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player \"(.+?)\"\(id=(.+?)\) is connected'
                disconnect_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player \"(.+?)\"\(id=(.+?)\) has been disconnected'
                kill_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player \"(.+?)\" ?\((?:id=.+?, )?pos=.+?\) killed by (.+?) with (.+?) from (.+?) meters'
                hit_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player \"(.+?)\".*?\[HP: (.+?)\] hit by (.+?) .*?(?:for (.+?) damage)?'
                suicide_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player \"(.+?)\" \(id=.+?\) committed suicide'
                death_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player \"(.+?)\" \(DEAD\) \(id=.+?\) died\\. Stats'

                for line in lines:
                    if re.search(connect_pattern, line):
                        timestamp, player, player_id = re.search(connect_pattern, line).groups()
                        events.append({'type': 'connection', 'timestamp': timestamp, 'player': player, 'player_id': player_id})
                    elif re.search(disconnect_pattern, line):
                        timestamp, player, player_id = re.search(disconnect_pattern, line).groups()
                        events.append({'type': 'disconnection', 'timestamp': timestamp, 'player': player, 'player_id': player_id})
                    elif re.search(kill_pattern, line):
                        timestamp, player, killer, weapon, distance = re.search(kill_pattern, line).groups()
                        events.append({'type': 'kill', 'timestamp': timestamp, 'player': player, 'killer': killer, 'weapon': weapon, 'distance': distance})
                    elif re.search(suicide_pattern, line):
                        timestamp, player = re.search(suicide_pattern, line).groups()
                        events.append({'type': 'suicide', 'timestamp': timestamp, 'player': player, 'cause': 'Suicide'})
                    elif re.search(death_pattern, line):
                        timestamp, player = re.search(death_pattern, line).groups()
                        if not any(e['type'] == 'suicide' and e['player'] == player for e in events[-10:]):
                            events.append({'type': 'death', 'timestamp': timestamp, 'player': player, 'cause': 'Causes naturelles'})
                    elif re.search(hit_pattern, line):
                        timestamp, player, hp, attacker, damage = re.search(hit_pattern, line).groups()
                        events.append({'type': 'hit', 'timestamp': timestamp, 'player': player, 'hp': hp or 'unknown', 'attacker': attacker or 'unknown', 'damage': damage or 'unknown'})
        except Exception as e:
            print(f"Erreur lors de l'analyse du fichier .ADM : {e}")

    ljson_files = glob.glob("Mystic_SourceLog_*.ljson")
    for file in ljson_files:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    if not isinstance(item, dict):
                        continue

                    event_type = item.get("event")

                    if event_type == "INFECTED_DEATH":
                        events.append({
                            "type": "zombie_kill",
                            "timestamp": item.get("ts", "00:00:00").split("T")[1],
                            "player": item.get("player", {}).get("name", "inconnu"),
                            "weapon": item.get("data", {}).get("ammo"),
                            "distance": item.get("data", {}).get("distance")
                        })

                    elif event_type == "ANIMAL_DEATH":
                        events.append({
                            "type": "animal_kill",
                            "timestamp": item.get("ts", "00:00:00").split("T")[1],
                            "player": item.get("player", {}).get("name", "inconnu"),
                            "weapon": item.get("data", {}).get("ammo"),
                            "distance": item.get("data", {}).get("distance")
                        })

                    elif "type" in item:
                        events.append({
                            "type": item.get("type", "unknown"),
                            "timestamp": item.get("timestamp", "00:00:00"),
                            "player": item.get("player", "inconnu"),
                            "player_id": item.get("player_id"),
                            "killer": item.get("killer"),
                            "weapon": item.get("weapon"),
                            "distance": item.get("distance"),
                            "attacker": item.get("attacker"),
                            "hp": item.get("hp"),
                            "damage": item.get("damage"),
                            "cause": item.get("cause")
                        })
        except Exception as e:
            print(f"Erreur lecture {file} : {e}")

    events.sort(key=lambda x: x.get('timestamp', '00:00:00').replace(":", ""))
    return events


def filter_events(events, event_type, limit=10):
    return [e for e in events if e['type'] == event_type][-limit:] if events else []


if __name__ == "__main__":
    events = parse_dayz_log()
    if events:
        print(f"Nombre total d'événements récupérés: {len(events)}")
        for event_type in ['connection', 'disconnection', 'kill', 'suicide', 'death', 'hit', 'zombie_kill', 'animal_kill']:
            filtered = filter_events(events, event_type, 3)
            print(f"\n{event_type.upper()} ({len(filtered)} événements):")
            for event in filtered:
                print(f"- {event['timestamp']} | {event['player']}")
    else:
        print("Aucun événement trouvé")
