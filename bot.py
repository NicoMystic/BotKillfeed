import discord
from discord.ext import commands, tasks
from ConfigCompteMystic import TOKEN
from dayz_status import ping_dayz_server
from dayz_log_parser import parse_dayz_log, filter_events
# Importer le gestionnaire de killboard
from killboard import register_commands as register_killboard_commands
import time
from datetime import datetime, timedelta
import json
import os
import re
import paramiko
import sqlite3

# Identifiants
SERVER_IP = "193.25.252.91"
SERVER_PORT = 2331  # Port QUERY
STATUS_CHANNEL_ID = 1353433252114858135  # ID du salon de statut
EVENTS_CHANNEL_ID = 1200564887995302059  # Salon pour les événements
PLAYER_ACTIVITY_CHANNEL_ID = 1200564819330347109  # Salon pour les connexions/déconnexions
CONFIG_FILE = "config.json"
LOG_FILE = "uptime_logs.txt"
PLAYER_ACTIVITY_LOG_FILE = "player_activity_logs.txt"  # Nouveau fichier pour les logs d'activité des joueurs
DAYZ_LOG_FILE_PATH = '/193.25.252.91_2330/ServerProfile/DayZServer_x64.ADM'  # Chemin du fichier de logs de connexion/déconnexion

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

last_status = None
last_message = None
server_start_time = datetime.utcnow() - timedelta(hours=1)
notifications_enabled = set()
last_event_timestamp = ""  # Pour suivre le dernier événement traité

# Paramètres de connexion SFTP
SFTP_HOST = '193.25.252.91'
SFTP_PORT = 8822
SFTP_USERNAME = 'nicolasd'
SFTP_PASSWORD = '57!9d1QemdSOD['

# Prochains redémarrages aux heures fixes (00h, 4h, 8h, 12h, 16h, 20h)
def get_next_restart():
    now = datetime.utcnow() + timedelta(hours=1)
    hours_restart = [0, 4, 8, 12, 16, 20]
    for hour in hours_restart:
        candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate > now:
            return candidate - timedelta(hours=1)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=1)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"map": "Chernarus"}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def save_log(message):
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{datetime.utcnow().isoformat()}] {message}\n")

def save_player_activity_log(message):
    with open(PLAYER_ACTIVITY_LOG_FILE, 'a') as f:
        f.write(f"[{datetime.utcnow().isoformat()}] {message}\n")

def get_last_processed_event():
    config = load_config()
    return config.get("last_event_timestamp", "")

def save_last_processed_event(timestamp):
    config = load_config()
    config["last_event_timestamp"] = timestamp
    save_config(config)

# Fonction pour récupérer le fichier DayZServer_x64.ADM via SFTP
def retrieve_dayz_log_sftp():
    try:
        # Connexion au serveur SFTP
        transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
        transport.connect(username=SFTP_USERNAME, password=SFTP_PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)

        # Récupérer le fichier de logs
        local_path = 'DayZServer_x64.ADM'
        
        try:
            # Essayer le chemin principal
            sftp.get(DAYZ_LOG_FILE_PATH, local_path)
        except Exception as e:
            print(f"Erreur avec le chemin principal: {e}")
            # Essayer des chemins alternatifs
            try:
                sftp.get('/193.25.252.91_2330/DayZServer_x64.ADM', local_path)
            except Exception:
                try:
                    sftp.get('/home/nicolasd/193.25.252.91_2330/ServerProfile/DayZServer_x64.ADM', local_path)
                except Exception as e:
                    print(f"Toutes les tentatives ont échoué: {e}")
                    sftp.close()
                    transport.close()
                    return None

        sftp.close()
        transport.close()

        print(f"Fichier de log récupéré avec succès depuis {SFTP_HOST}.")
        return local_path
    except Exception as e:
        print(f"Erreur lors de la récupération du fichier SFTP : {e}")
        return None

# Fonction pour analyser les événements et gérer les nouveaux en temps réel
# Fonction pour analyser les événements et gérer les nouveaux en temps réel
async def process_new_events():
    global last_event_timestamp
    
    events_channel = bot.get_channel(EVENTS_CHANNEL_ID)
    player_activity_channel = bot.get_channel(PLAYER_ACTIVITY_CHANNEL_ID)
    
    if not events_channel or not player_activity_channel:
        print("Impossible de trouver les salons d'activité")
        return

    # Récupérer tous les événements
    events = parse_dayz_log()
    if not events:
        print("Aucun événement récupéré")
        return
        
    # Récupérer le dernier timestamp traité depuis le fichier de configuration
    last_timestamp = get_last_processed_event()
    
    # Filtre les nouveaux événements (ceux avec un timestamp supérieur au dernier traité)
    new_events = []
    latest_timestamp = last_timestamp
    
    for event in events:
        # Créer un timestamp numérique pour comparaison (HH:MM:SS → HHMMSS)
        current_ts = event['timestamp'].replace(':', '')
        last_ts = last_timestamp.replace(':', '')
        
        # Si le timestamp actuel est plus récent ou si c'est un nouvel événement d'aujourd'hui
        if current_ts > last_ts:
            new_events.append(event)
            if current_ts > latest_timestamp.replace(':', ''):
                latest_timestamp = event['timestamp']
    
    print(f"Nouveaux événements trouvés: {len(new_events)}")
    
    # Si nous avons des nouveaux événements, envoyez-les aux canaux appropriés
    for event in new_events:
        try:
            if event['type'] == 'connection':
                embed = discord.Embed(
                    title="👋 Connexion",
                    description=f"**{event['player']}** s'est connecté(e) au serveur",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"{event['timestamp']}")
                await player_activity_channel.send(embed=embed)
                save_player_activity_log(f"Connexion: {event['player']} à {event['timestamp']}")
                
            elif event['type'] == 'disconnection':
                embed = discord.Embed(
                    title="🚶 Déconnexion",
                    description=f"**{event['player']}** s'est déconnecté(e) du serveur",
                    color=discord.Color.orange()
                )
                embed.set_footer(text=f"{event['timestamp']}")
                await player_activity_channel.send(embed=embed)
                save_player_activity_log(f"Déconnexion: {event['player']} à {event['timestamp']}")
                
            elif event['type'] == 'kill':
                embed = discord.Embed(
                    title="☠️ Mort",
                    description=f"**{event['player']}** a été tué par **{event['killer']}**",
                    color=discord.Color.red()
                )
                embed.add_field(name="Arme", value=event['weapon'], inline=True)
                embed.add_field(name="Distance", value=f"{event['distance']}m", inline=True)
                embed.set_footer(text=f"{event['timestamp']}")
                await events_channel.send(embed=embed)
                save_player_activity_log(f"Kill: {event['player']} tué par {event['killer']} à {event['timestamp']}")
                # Ajouter cette ligne pour mettre à jour le killboard
                killboard_manager.process_kill_event(event)
                
            elif event['type'] == 'suicide':
                embed = discord.Embed(
                    title="💀 Suicide",
                    description=f"**{event['player']}** s'est suicidé",
                    color=discord.Color.dark_red()
                )
                embed.set_footer(text=f"{event['timestamp']}")
                await events_channel.send(embed=embed)
                save_player_activity_log(f"Suicide: {event['player']} à {event['timestamp']}")
                result = killboard_manager.process_kill_event(event)
                print(f"Killboard update result: {result}")
                
            elif event['type'] == 'death':
                embed = discord.Embed(
                    title="⚰️ Décès",
                    description=f"**{event['player']}** est mort de {event['cause']}",
                    color=discord.Color.dark_gray()
                )
                embed.set_footer(text=f"{event['timestamp']}")
                await events_channel.send(embed=embed)
                save_player_activity_log(f"Décès: {event['player']} de {event['cause']} à {event['timestamp']}")
                
            elif event['type'] == 'animal_kill':
                embed = discord.Embed(
                    title="🐺 Animal tué",
                    description=f"**{event['player']}** a tué un **animal**",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"{event['timestamp']}")
                await events_channel.send(embed=embed)
                killboard_manager.process_kill_event(event)

            elif event['type'] == 'zombie_kill':
                embed = discord.Embed(
                title="🧟 Zombie tué",
                description=f"**{event['player']}** a tué un **zombie**",
                color=discord.Color.purple()
                )
                embed.set_footer(text=f"{event['timestamp']}")
                await events_channel.send(embed=embed)
                killboard_manager.process_kill_event(event)



            elif event['type'] == 'hit' and 'player' in event and 'attacker' in event:
                # Optionnel: notifications pour les hits (peut générer beaucoup de messages)
                if 'Player' in event['attacker']:  # Seulement les hits PvP
                    embed = discord.Embed(
                        title="💥 Attaque PvP",
                        description=f"**{event['player']}** a été attaqué par **{event['attacker']}**",
                        color=discord.Color.gold()
                    )
                    if 'damage' in event and event['damage'] != "unknown":
                        embed.add_field(name="Dégâts", value=f"{event['damage']}", inline=True)
                    embed.set_footer(text=f"{event['timestamp']}")
                    await events_channel.send(embed=embed)
        
        except Exception as e:
            print(f"Erreur lors du traitement de l'événement {event['type']}: {e}")
    
    # Mettre à jour le dernier timestamp traité
    if latest_timestamp != last_timestamp:
        save_last_processed_event(latest_timestamp)
        last_event_timestamp = latest_timestamp

@bot.event
async def on_ready():
    print(f"{bot.user.name} connecté.")
    global killboard_manager
    killboard_manager = register_killboard_commands(bot)
    check_server.start()
    real_time_events.start()
    print("Tâches programmées lancées.")

@tasks.loop(minutes=3)
async def check_server():
    global last_status, last_message
    config = load_config()
    status_channel = bot.get_channel(STATUS_CHANNEL_ID)
    events_channel = bot.get_channel(EVENTS_CHANNEL_ID)

    if not status_channel or not events_channel:
        print("Un ou plusieurs salons introuvables !")
        return

    status, message, ping = ping_dayz_server(SERVER_IP, SERVER_PORT, return_ping=True)

    uptime = datetime.utcnow() - server_start_time
    uptime_str = f"{uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}min"
    next_restart = get_next_restart()
    time_to_restart = next_restart - datetime.utcnow()
    restart_str = f"{time_to_restart.seconds // 3600}h {(time_to_restart.seconds // 60) % 60}min"

    map_name = config.get("map", "Chernarus")
    map_links = {
        "Chernarus": ("https://dayzaide.fr//Images_Dayz/FondDayz/Chernarus.jpg", "https://www.izurvive.com/chernarusplus/"),
        "Livonia": ("https://i.imgur.com/s1WTOUe.png", "https://www.izurvive.com/livonia/"),
        "Namalsk": ("https://i.imgur.com/rnZADnH.png", "https://www.izurvive.com/namalsk/"),
    }
    map_img, map_url = map_links.get(map_name, map_links["Chernarus"])

    embed = discord.Embed(
        title="🧭 Statut du serveur DayZ",
        description=message,
        color=discord.Color.green() if status else discord.Color.red()
    )
    embed.add_field(name="🌍 Carte", value=f"[{map_name}]({map_url})", inline=True)
    embed.add_field(name="🕒 Uptime", value=uptime_str, inline=True)
    embed.add_field(name="📡 Ping moyen", value=f"~{ping} ms", inline=True)
    embed.add_field(name="♻️ Prochain redémarrage", value=restart_str, inline=True)
    embed.set_footer(text="Mis à jour automatiquement par Mystic Bot")
    embed.set_thumbnail(url=map_img)

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="🔁 Rafraîchir", style=discord.ButtonStyle.green, custom_id="refresh_status"))
    view.add_item(discord.ui.Button(label="🕒 Restart", style=discord.ButtonStyle.blurple, custom_id="restart_list"))
    view.add_item(discord.ui.Button(label="🔔 Activer", style=discord.ButtonStyle.primary, custom_id="notif_on"))
    view.add_item(discord.ui.Button(label="🔕 Désactiver", style=discord.ButtonStyle.secondary, custom_id="notif_off"))

    if last_message:
        try:
            await last_message.delete()
        except:
            pass

    last_message = await status_channel.send(embed=embed, view=view)
    save_log(f"Serveur {'ONLINE' if status else 'OFFLINE'} | Ping: {ping} ms")

    if last_status is not None and last_status != status:
        if not status and events_channel:
            await events_channel.send("⚠️ **ALERTE** : **Mise à jour** du serveur !")
            for user_id in notifications_enabled:
                try:
                    user = await bot.fetch_user(user_id)
                    await user.send("⚠️ Le serveur DayZ est tombé hors-ligne !")
                except Exception as e:
                    print(f"Erreur notification: {e}")

    last_status = status

# Nouvelle tâche pour vérifier les événements en temps réel (toutes les 30 secondes)
@tasks.loop(seconds=30)
async def real_time_events():
    try:
        await process_new_events()
    except Exception as e:
        print(f"Erreur lors du traitement des événements en temps réel: {e}")

@bot.command()
async def status(ctx):
    await check_server()
    await ctx.send("✅ Statut mis à jour.")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    user_id = interaction.user.id
    if interaction.data.get("custom_id") == "refresh_status":
        await check_server()
        await interaction.response.send_message("🔁 Statut mis à jour.", ephemeral=True)
    elif interaction.data.get("custom_id") == "restart_list":
        horaires = """🔄 **Redémarrages automatiques :**\n• 00h00\n• 04h00\n• 08h00\n• 12h00\n• 16h00\n• 20h00"""
        await interaction.response.send_message(horaires, ephemeral=True)
    elif interaction.data.get("custom_id") == "notif_on":
        notifications_enabled.add(user_id)
        await interaction.response.send_message("🔔 Notifications activées.", ephemeral=True)
    elif interaction.data.get("custom_id") == "notif_off":
        notifications_enabled.discard(user_id)
        await interaction.response.send_message("🔕 Notifications désactivées.", ephemeral=True)

@bot.command()
async def player_stats(ctx):
    events = parse_dayz_log()
    
    if not events:
        await ctx.send("❌ Impossible de récupérer les informations des joueurs.")
        return
        
    # Récupérer les connexions et déconnexions les plus récentes
    connections = filter_events(events, 'connection', 5)
    disconnections = filter_events(events, 'disconnection', 5)
    kills = filter_events(events, 'kill', 5)
    
    # Créer un embed
    embed = discord.Embed(
        title="📊 Statistiques des joueurs",
        description="Voici les activités récentes des joueurs sur le serveur",
        color=discord.Color.blue()
    )
    
    # Connexions récentes
    if connections:
        connections_text = "\n".join([f"{e['timestamp']} • **{e['player']}**" for e in connections])
        embed.add_field(name="🟢 Connexions récentes", value=connections_text, inline=False)
    else:
        embed.add_field(name="🟢 Connexions récentes", value="Aucune connexion récente trouvée", inline=False)
    
    # Déconnexions récentes
    if disconnections:
        disconnections_text = "\n".join([f"{e['timestamp']} • **{e['player']}**" for e in disconnections])
        embed.add_field(name="🔴 Déconnexions récentes", value=disconnections_text, inline=False)
    else:
        embed.add_field(name="🔴 Déconnexions récentes", value="Aucune déconnexion récente trouvée", inline=False)
    
    # Kills récents
    if kills:
        kills_text = "\n".join([f"{e['timestamp']} • **{e['player']}** tué par **{e['killer']}** ({e['weapon']})" for e in kills])
        embed.add_field(name="☠️ Kills récents", value=kills_text, inline=False)
    else:
        embed.add_field(name="☠️ Kills récents", value="Aucun kill récent trouvé", inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
async def refresh_events(ctx):
    """Force la vérification des nouveaux événements"""
    await ctx.send("🔍 Recherche de nouveaux événements...")
    await process_new_events()
    await ctx.send("✅ Traitement des événements terminé.")

@bot.command()
async def test_score(ctx, player_name="TestPlayer", kill_type="survivor"):
    """Commande de test pour ajouter un score manuellement"""
    success = killboard_manager.update_player_score(player_name, kill_type)
    if success:
        await ctx.send(f"✅ Score ajouté pour {player_name} - Type: {kill_type}")
    else:
        await ctx.send("❌ Échec de l'ajout du score")


@bot.command()
async def add_test_score(ctx):
    """Test direct de la base de données"""
    try:
        # Connexion directe à la base de données
        conn = sqlite3.connect('player_scores.db')
        cursor = conn.cursor()
        
        # Créer la table si elle n'existe pas
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            player_name TEXT PRIMARY KEY,
            total_score INTEGER DEFAULT 0,
            survivor_kills INTEGER DEFAULT 0,
            ai_kills INTEGER DEFAULT 0, 
            animal_kills INTEGER DEFAULT 0,
            zombie_kills INTEGER DEFAULT 0
        )
        ''')
        
        # Insérer un enregistrement de test
        cursor.execute('''
        INSERT OR REPLACE INTO scores 
        (player_name, total_score, survivor_kills, ai_kills, animal_kills, zombie_kills)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', ("TestPlayer", 10, 2, 0, 0, 0))
        
        conn.commit()
        conn.close()
        
        await ctx.send("✅ Score de test ajouté directement dans la base de données.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors du test de la base de données: {str(e)}")

@bot.command()

async def event_log(ctx, limit: int = 10):
    """Affiche les derniers événements des logs du serveur"""
    if limit > 20:
        limit = 20  # Limiter à 20 événements maximum
    
    events = parse_dayz_log()
    if not events:
        await ctx.send("❌ Impossible de récupérer les événements.")
        return
    
    # Filtrer uniquement les événements intéressants
    filtered_events = [e for e in events if e['type'] in ['connection', 'disconnection', 'kill']]
    
    # Prendre les X derniers
    recent = filtered_events[-limit:]
    
    if not recent:
        await ctx.send("❌ Aucun événement trouvé dans les logs.")
        return
    
    embed = discord.Embed(
        title="📜 Journal des événements",
        description=f"Les {len(recent)} derniers événements sur le serveur",
        color=discord.Color.blue()
    )
    
    for i, event in enumerate(recent, 1):
        event_desc = ""
        if event['type'] == 'connection':
            event_desc = f"**{event['player']}** s'est connecté"
        elif event['type'] == 'disconnection':
            event_desc = f"**{event['player']}** s'est déconnecté"
        elif event['type'] == 'kill':
            event_desc = f"**{event['player']}** a été tué par **{event['killer']}** avec {event['weapon']}"
            # RETIREZ LA LIGNE CI-DESSOUS
            # killboard_manager.process_kill_event(event)
        
        embed.add_field(
            name=f"{i}. {event['timestamp']}",
            value=event_desc,
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)  # Uniquement pour les administrateurs
async def remove_player(ctx, player_name):
    """Retire un joueur du tableau des scores"""
    try:
        conn = sqlite3.connect('player_scores.db')
        cursor = conn.cursor()
        
        # Vérifier si le joueur existe
        cursor.execute('SELECT * FROM scores WHERE player_name = ?', (player_name,))
        if cursor.fetchone() is None:
            await ctx.send(f"❌ Le joueur **{player_name}** n'existe pas dans le tableau des scores.")
            conn.close()
            return
        
        # Supprimer le joueur
        cursor.execute('DELETE FROM scores WHERE player_name = ?', (player_name,))
        conn.commit()
        conn.close()
        
        await ctx.send(f"✅ Le joueur **{player_name}** a été retiré du tableau des scores.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors de la suppression du joueur: {str(e)}")

@bot.command()
@commands.has_permissions(administrator=True)  # Uniquement pour les administrateurs
async def reset_killboard(ctx):
    """Réinitialise tout le tableau des scores"""
    try:
        conn = sqlite3.connect('player_scores.db')
        cursor = conn.cursor()
        
        # Supprimer tous les scores
        cursor.execute('DELETE FROM scores')
        conn.commit()
        conn.close()
        
        await ctx.send("✅ Le tableau des scores a été entièrement réinitialisé.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors de la réinitialisation du tableau: {str(e)}")



















@bot.command()
async def debug_log(ctx):
    """Commande pour déboguer le parser de logs"""
    await ctx.send("⏳ Analyse des logs en cours...")
    
    # Tester la récupération du fichier SFTP
    log_file = retrieve_dayz_log_sftp()
    if not log_file:
        await ctx.send("❌ Échec de la récupération du fichier de logs via SFTP.")
        # Vérifier si on a un fichier local
        if os.path.exists("DayZServer_x64.ADM"):
            await ctx.send("✅ Fichier local disponible, utilisation de celui-ci.")
            log_file = "DayZServer_x64.ADM"
        else:
            await ctx.send("❌ Aucun fichier de logs disponible, localement ou via SFTP.")
            return
    else:
        await ctx.send(f"✅ Fichier de logs récupéré avec succès: {log_file}")
    
    # Vérifier la taille du fichier
    file_size = os.path.getsize(log_file)
    await ctx.send(f"📄 Taille du fichier: {file_size} octets")
    
    # Analyser les événements
    try:
        events = parse_dayz_log()
        
        if not events:
            await ctx.send("❌ Aucun événement trouvé dans les logs.")
            return
            
        count_by_type = {}
        for event in events:
            event_type = event['type']
            count_by_type[event_type] = count_by_type.get(event_type, 0) + 1
        
        result = "📊 **Résultat de l'analyse:**\n\n"
        result += f"Total d'événements: **{len(events)}**\n\n"
        
        for event_type, count in count_by_type.items():
            result += f"• **{event_type}**: {count} événements\n"
            
        # Exemples de chaque type d'événement
        result += "\n**Derniers événements de chaque type:**\n"
        for event_type in count_by_type.keys():
            examples = filter_events(events, event_type, 1)
            if examples:
                example = examples[0]
                result += f"\n**{event_type}**: `{example['timestamp']}` - "
                
                if event_type == 'connection':
                    result += f"`{example['player']} connecté`"
                elif event_type == 'disconnection':
                    result += f"`{example['player']} déconnecté`"
                elif event_type == 'kill':
                    result += f"`{example['player']} tué par {example['killer']}`"
                elif event_type == 'hit':
                    result += f"`{example['player']} touché par {example['attacker']}`"
        
        # Information sur le dernier événement traité
        last_timestamp = get_last_processed_event()
        result += f"\n\n**Dernier événement traité:** `{last_timestamp or 'Aucun'}`"
        
        await ctx.send(result)
    except Exception as e:
        await ctx.send(f"❌ Erreur lors de l'analyse des logs: `{str(e)}`")

# Lancement du bot
if __name__ == "__main__":
    bot.run(TOKEN)
