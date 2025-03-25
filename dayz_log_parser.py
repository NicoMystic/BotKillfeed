import re
import os
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
        # Connexion au serveur SFTP
        transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
        transport.connect(username=SFTP_USERNAME, password=SFTP_PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)

        # Récupérer le fichier de logs
        local_path = 'DayZServer_x64.ADM'
        
        # Essayer différents chemins possibles
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

def parse_dayz_log(custom_file=None):
    log_file_path = custom_file or retrieve_dayz_log_sftp()
    if not log_file_path and os.path.exists("DayZServer_x64.ADM"):
        log_file_path = "DayZServer_x64.ADM"
        print("Utilisation du fichier local existant")
    
    if not log_file_path:
        print("Aucun fichier de log disponible")
        return None
    
    # Patterns correspondant spécifiquement au format du fichier DayZServer_x64.ADM
    connect_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player "(.+?)"\(id=(.+?)\) is connected'
    disconnect_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player "(.+?)"\(id=(.+?)\) has been disconnected'
    # Vérifiez que ce pattern correspond bien au format dans les logs
    kill_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player "(.+?)" ?\((?:id=.+?, )?pos=.+?\) killed by (.+?) with (.+?) from (.+?) meters'
    hit_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player "(.+?)".*?\[HP: (.+?)\] hit by (.+?) .*?(?:for (.+?) damage)?'
    
    # Nouveaux patterns pour les suicides et morts naturelles
    suicide_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player "(.+?)" \(id=.+?\) committed suicide'
    death_pattern = r'(\d{2}:\d{2}:\d{2}) \| Player "(.+?)" \(DEAD\) \(id=.+?\) died\. Stats'
    
    events = []
    
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
            lines = file.readlines()
            
            for line in lines:
                # Connexion
                connect_match = re.search(connect_pattern, line)
                if connect_match:
                    timestamp, player, player_id = connect_match.groups()
                    events.append({
                        'type': 'connection',
                        'timestamp': timestamp,
                        'player': player,
                        'player_id': player_id
                    })
                    continue
                
                # Déconnexion
                disconnect_match = re.search(disconnect_pattern, line)
                if disconnect_match:
                    timestamp, player, player_id = disconnect_match.groups()
                    events.append({
                        'type': 'disconnection',
                        'timestamp': timestamp,
                        'player': player,
                        'player_id': player_id
                    })
                    continue
                
                # Kill (mort d'un joueur)
                kill_match = re.search(kill_pattern, line)
                if kill_match:
                    timestamp, player, killer, weapon, distance = kill_match.groups()
                    events.append({
                        'type': 'kill',
                        'timestamp': timestamp,
                        'player': player,
                        'killer': killer,
                        'weapon': weapon,
                        'distance': distance
                    })
                    continue
                
                # Suicide
                suicide_match = re.search(suicide_pattern, line)
                if suicide_match:
                    timestamp, player = suicide_match.groups()
                    events.append({
                        'type': 'suicide',
                        'timestamp': timestamp,
                        'player': player,
                        'cause': 'Suicide'
                    })
                    continue
                    
                # Mort naturelle (après suicide ou autre)
                death_match = re.search(death_pattern, line)
                if death_match:
                    timestamp, player = death_match.groups()
                    # Vérifier si un suicide correspondant existe déjà
                    suicide_exists = False
                    for event in events[-10:]:  # Vérifier les 10 derniers événements
                        if event['type'] == 'suicide' and event['player'] == player:
                            suicide_exists = True
                            break
                    
                    if not suicide_exists:
                        events.append({
                            'type': 'death',
                            'timestamp': timestamp,
                            'player': player,
                            'cause': 'Causes naturelles'
                        })
                    continue
                
                # Hit (dommage)
                hit_match = re.search(hit_pattern, line)
                if hit_match:
                    groups = hit_match.groups()
                    timestamp = groups[0]
                    player = groups[1]
                    hp = groups[2] if len(groups) > 2 else "unknown"
                    attacker = groups[3] if len(groups) > 3 else "unknown"
                    damage = groups[4] if len(groups) > 4 and groups[4] else "unknown"
                    
                    events.append({
                        'type': 'hit',
                        'timestamp': timestamp,
                        'player': player,
                        'hp': hp,
                        'attacker': attacker,
                        'damage': damage
                    })
        
        # Trier les événements par timestamp
        events.sort(key=lambda x: x['timestamp'])
        return events
            
    except Exception as e:
        print(f"Erreur lors de l'analyse du fichier de logs: {e}")
        return None

# Fonction utilitaire pour filtrer les événements par type et limiter le nombre
def filter_events(events, event_type, limit=10):
    if not events:
        return []
    filtered = [e for e in events if e['type'] == event_type]
    return filtered[-limit:]  # Retourne les X derniers événements du type spécifié

# Test de la fonction si appelée directement
if __name__ == "__main__":
    events = parse_dayz_log()
    if events:
        print(f"Nombre total d'événements récupérés: {len(events)}")
        
        # Afficher quelques exemples de chaque type
        for event_type in ['connection', 'disconnection', 'kill', 'suicide', 'death', 'hit']:
            filtered = filter_events(events, event_type, 3)
            print(f"\n{event_type.upper()} ({len(filtered)} événements):")
            for event in filtered:
                print(f"- {event['timestamp']} | {event['player']}")
    else:
        print("Aucun événement trouvé")