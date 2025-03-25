import json
import os
import glob
from datetime import datetime

# Position de lecture pour les fichiers LJSON
last_ljson_position = 0
current_ljson_file = None

def find_latest_ljson_log(log_dir="$profile:"):
    """Trouve le fichier de log LJSON le plus récent
    
    Args:
        log_dir: Le répertoire où chercher les logs (par défaut: "$profile:")
                 Remplacer par le chemin réel où sont stockés les fichiers
    
    Returns:
        str: Chemin du fichier le plus récent, ou None si aucun trouvé
    """
    real_dir = log_dir.replace("$profile:", "")  # Remplacer par le vrai chemin si nécessaire
    log_pattern = os.path.join(real_dir, "Mystic_SourceLogs_*.ljson")
    log_files = glob.glob(log_pattern)
    
    if not log_files:
        return None
    
    # Trier par date de modification (le plus récent en premier)
    log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    return log_files[0]

def read_ljson_events(file_path, last_position=0):
    """Lit les nouveaux événements du fichier LJSON
    
    Args:
        file_path: Chemin vers le fichier LJSON
        last_position: Position de lecture dans le fichier
        
    Returns:
        tuple: (liste des nouveaux événements, nouvelle position de lecture)
    """
    if not file_path or not os.path.exists(file_path):
        return [], last_position
    
    current_size = os.path.getsize(file_path)
    
    # Si le fichier a été tronqué ou est nouveau, réinitialiser la position
    if current_size < last_position:
        last_position = 0
    
    new_events = []
    if current_size > last_position:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.seek(last_position)
            for line in f:
                try:
                    line = line.strip()
                    if not line:
                        continue
                    event = json.loads(line)
                    new_events.append(event)
                except json.JSONDecodeError as e:
                    print(f"Erreur de décodage JSON: {e} - Ligne: {line[:100]}")
                except Exception as e:
                    print(f"Erreur lors de la lecture du fichier LJSON: {e}")
            
            last_position = f.tell()
    
    return new_events, last_position

def get_event_timestamp(event):
    """Récupère le timestamp d'un événement au format datetime
    
    Args:
        event: Dictionnaire d'événement LJSON
        
    Returns:
        datetime: Objet datetime du timestamp, ou None si non trouvé
    """
    ts_str = event.get("ts", "")
    if not ts_str:
        return None
    
    try:
        # Format attendu: "2023-01-31T14:25:10"
        return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None

def process_ljson_kills(events, killboard_manager):
    """Traite les événements de kill du fichier LJSON pour le killboard
    
    Args:
        events: Liste des événements à traiter
        killboard_manager: Instance du gestionnaire de killboard
    
    Returns:
        int: Nombre de kills traités avec succès
    """
    kill_count = 0
    kill_types = ["PLAYER_DEATH", "ANIMAL_DEATH", "INFECTED_DEATH", 
                 "PLAYER_LETHAL_DAMAGE", "ANIMAL_LETHAL_DAMAGE", "INFECTED_LETHAL_DAMAGE"]
    
    for event in events:
        # Vérifier si c'est un événement de mort/kill
        event_type = event.get("event", "")
        if event_type in kill_types:
            data = event.get("data", {})
            
            # Format attendu: {"tag":"#death","target":...,"source":...,"killer":...,"distance":...}
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    data = {}
            
            # Extraire les informations pertinentes
            killer_info = None
            
            # Essayer de trouver le tueur dans différents formats possibles
            if "killer" in data and data["killer"] != "null":
                killer_info = data["killer"]
            
            # Si killer_info n'est pas trouvé ou n'est pas utilisable
            if not killer_info:
                continue
                
            # Extraire le nom du joueur
            killer_name = ""
            if isinstance(killer_info, dict) and "name" in killer_info:
                killer_name = killer_info["name"]
            elif isinstance(killer_info, str) and "Player" in killer_info:
                # Essayer d'extraire avec regex
                import re
                match = re.search(r'Player "([^"]+)"', killer_info)
                if match:
                    killer_name = match.group(1)
            
            if not killer_name:
                continue
                
            # Déterminer le type de cible
            victim_type = "unknown"
            
            if "PLAYER_" in event_type:
                victim_type = "survivor"
            elif "ANIMAL_" in event_type:
                victim_type = "animal"
            elif "INFECTED_" in event_type:
                victim_type = "zombie"
            
            # Mettre à jour le killboard
            if victim_type != "unknown":
                print(f"Ajout de kill: {killer_name} a tué un {victim_type}")
                result = killboard_manager.update_player_score(killer_name, victim_type)
                if result:
                    kill_count += 1
    
    return kill_count

def format_event_data(event_type, data):
    """Formate les données d'événement selon son type
    
    Args:
        event_type: Type d'événement (str)
        data: Données à formater (dict ou str)
    
    Returns:
        str: Représentation formatée des données
    """
    # Convertir les données en dict si c'est une chaîne JSON
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            return data
    
    if not isinstance(data, dict):
        return str(data)
    
    # Formater selon le type d'événement
    if "DEATH" in event_type or "LETHAL_DAMAGE" in event_type:
        target = data.get("target", {})
        killer = data.get("killer", {})
        source = data.get("source", "Inconnu")
        distance = data.get("distance", "Inconnue")
        
        target_name = "Inconnu"
        killer_name = "Inconnu"
        
        if isinstance(target, dict) and "name" in target:
            target_name = target["name"]
        elif isinstance(target, str) and "Player" in target:
            import re
            match = re.search(r'Player "([^"]+)"', target)
            if match:
                target_name = match.group(1)
        
        if isinstance(killer, dict) and "name" in killer:
            killer_name = killer["name"]
        elif isinstance(killer, str) and "Player" in killer:
            import re
            match = re.search(r'Player "([^"]+)"', killer)
            if match:
                killer_name = match.group(1)
        
        return f"Victime: {target_name}\nTueur: {killer_name}\nArme: {source}\nDistance: {distance}"
    
    if "HIT" in event_type or "DAMAGE" in event_type:
        return f"Source: {data.get('source', 'Inconnu')}\nCible: {data.get('target', 'Inconnu')}\nZone: {data.get('zone', 'Inconnue')}\nDégâts: {data.get('dmgHealth', 'Inconnus')}"
    
    if "ITEM_" in event_type:
        item = data.get("item", "Inconnu")
        if isinstance(item, dict):
            return f"Objet: {item.get('type', 'Inconnu')}\nID: {item.get('id', 'Inconnu')}"
        return f"Objet: {item}"
    
    if "PLAYER_MOVEMENT" in event_type:
        player = event.get("player", {})
        if isinstance(player, dict):
            return f"Joueur: {player.get('name', 'Inconnu')}\nPosition: {player.get('position', 'Inconnue')}\nDirection: {player.get('direction', 'Inconnue')}"
        return f"Mouvement: {data.get('tag', 'Inconnu')}"
    
    # Format générique pour les autres types
    formatted = []
    for key, value in data.items():
        if isinstance(value, dict):
            formatted.append(f"{key}: {{{', '.join([f'{k}: {v}' for k, v in value.items()])}}}")
        else:
            formatted.append(f"{key}: {value}")
    
    return "\n".join(formatted)