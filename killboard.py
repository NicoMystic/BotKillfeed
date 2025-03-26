import sqlite3
import discord
from discord.ext import commands
import re
from datetime import datetime 

# Constantes pour les points
POINTS_SURVIVANT = 5
POINTS_AI = 4
POINTS_ANIMAL = 2
POINTS_ZOMBIE = 1

class KillboardManager:
    def __init__(self, db_name='player_scores.db'):
        self.db_name = db_name
        self._init_database()
    
    def _init_database(self):
        """Initialiser la base de données des scores"""
        try:
            conn = sqlite3.connect(self.db_name)
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
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erreur lors de l'initialisation de la base de données: {e}")
    
    def get_player_scores(self):
        """Récupérer tous les scores des joueurs"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Récupérer tous les scores
            cursor.execute('SELECT * FROM scores')
            rows = cursor.fetchall()
            
            scores = {}
            for row in rows:
                scores[row[0]] = {
                    'total': row[1],
                    'survivors': row[2],
                    'ai': row[3],
                    'animals': row[4],
                    'zombies': row[5]
                }
            
            conn.close()
            return scores
        except Exception as e:
            print(f"Erreur lors de la récupération des scores: {e}")
            return {}
    
    def update_player_score(self, player_name, kill_type):
        """Mettre à jour le score d'un joueur"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Déterminer les points en fonction du type de kill
            points = 0
            column = ''
            
            if kill_type == 'survivor':
                points = POINTS_SURVIVANT
                column = 'survivor_kills'
            elif kill_type == 'ai':
                points = POINTS_AI
                column = 'ai_kills'
            elif kill_type == 'animal':
                points = POINTS_ANIMAL
                column = 'animal_kills'
            elif kill_type == 'zombie':
                points = POINTS_ZOMBIE
                column = 'zombie_kills'
            else:
                conn.close()
                return False
            
            # Vérifier si le joueur existe déjà
            cursor.execute('SELECT * FROM scores WHERE player_name = ?', (player_name,))
            row = cursor.fetchone()
            
            if row:
                # Mettre à jour le score existant
                cursor.execute(f'UPDATE scores SET total_score = total_score + ?, {column} = {column} + 1 WHERE player_name = ?', 
                              (points, player_name))
            else:
                # Créer une nouvelle entrée pour le joueur
                default_values = {'survivor_kills': 0, 'ai_kills': 0, 'animal_kills': 0, 'zombie_kills': 0}
                default_values[column] = 1
                
                cursor.execute('INSERT INTO scores (player_name, total_score, survivor_kills, ai_kills, animal_kills, zombie_kills) VALUES (?, ?, ?, ?, ?, ?)', 
                              (player_name, points, 
                               default_values['survivor_kills'] if column != 'survivor_kills' else 1,
                               default_values['ai_kills'] if column != 'ai_kills' else 1, 
                               default_values['animal_kills'] if column != 'animal_kills' else 1,
                               default_values['zombie_kills'] if column != 'zombie_kills' else 1))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur lors de la mise à jour des scores: {e}")
            return False
    
    def determine_kill_type(self, killer_info, target_info=None, weapon=None):
        """Déterminer le type de kill en fonction des informations disponibles"""
        print(f"Determining kill type: killer={killer_info}, target={target_info}, weapon={weapon}")
    
    # Patterns pour identifier les types de kill
        survivor_pattern = r'Player "([^"]+)"'
        ai_pattern = r'AI "([^"]+)"'
        animal_patterns = ['Wolf', 'Bear', 'Animal']
        zombie_patterns = ['Infected', 'InfectedAI', 'Zombie']
    
    # Vérifier si c'est un joueur qui a tué
        if re.search(survivor_pattern, killer_info):
            # Maintenant déterminer ce qui a été tué
            if target_info:
                if re.search(survivor_pattern, target_info):
                    return 'survivor'
                elif re.search(ai_pattern, target_info):
                    return 'ai'
                elif any(animal in target_info for animal in animal_patterns):
                    return 'animal'
                elif any(zombie in target_info for zombie in zombie_patterns):
                    return 'zombie'
        
            # Si on ne peut pas déterminer par la cible, essayons par l'arme
            if weapon:
                if any(animal in weapon for animal in animal_patterns):
                    return 'animal'
                elif any(zombie in weapon for zombie in zombie_patterns):
                    return 'zombie'
        
        print(f"Could not determine kill type")
        return 'unknown'

    def get_top_players(self, limit=10):
        """Récupérer les meilleurs joueurs"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            # Récupérer les meilleurs joueurs
            cursor.execute('''
            SELECT player_name, total_score, survivor_kills, ai_kills, animal_kills, zombie_kills 
            FROM scores 
            ORDER BY total_score DESC 
            LIMIT ?
            ''', (limit,))
            
            top_players = cursor.fetchall()
            conn.close()
            
            return top_players
        except Exception as e:
            print(f"Erreur lors de la récupération des meilleurs joueurs: {e}")
            return []
    
    def reset_scores(self):
        """Réinitialiser tous les scores"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM scores')
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            print(f"Erreur lors de la réinitialisation des scores: {e}")
            return False
    
    # Remplacez la fonction process_kill_event (vers la ligne 179) par celle-ci:
import sqlite3
import discord
from discord.ext import commands
import re
from datetime import datetime 

# Constantes pour les points
POINTS_SURVIVANT = 5
POINTS_AI = 4
POINTS_ANIMAL = 2
POINTS_ZOMBIE = 1

class KillboardManager:
    def __init__(self, db_name='player_scores.db'):
        self.db_name = db_name
        self._init_database()

    def _init_database(self):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
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
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erreur lors de l'initialisation de la base de données: {e}")

    def update_player_score(self, player_name, kill_type):
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            points = 0
            column = ''
            if kill_type == 'survivor':
                points = POINTS_SURVIVANT
                column = 'survivor_kills'
            elif kill_type == 'ai':
                points = POINTS_AI
                column = 'ai_kills'
            elif kill_type == 'animal':
                points = POINTS_ANIMAL
                column = 'animal_kills'
            elif kill_type == 'zombie':
                points = POINTS_ZOMBIE
                column = 'zombie_kills'
            else:
                conn.close()
                return False
            cursor.execute('SELECT * FROM scores WHERE player_name = ?', (player_name,))
            row = cursor.fetchone()
            if row:
                cursor.execute(f'UPDATE scores SET total_score = total_score + ?, {column} = {column} + 1 WHERE player_name = ?', 
                              (points, player_name))
            else:
                default_values = {'survivor_kills': 0, 'ai_kills': 0, 'animal_kills': 0, 'zombie_kills': 0}
                default_values[column] = 1
                cursor.execute('INSERT INTO scores (player_name, total_score, survivor_kills, ai_kills, animal_kills, zombie_kills) VALUES (?, ?, ?, ?, ?, ?)', 
                              (player_name, points, 
                               default_values['survivor_kills'],
                               default_values['ai_kills'], 
                               default_values['animal_kills'],
                               default_values['zombie_kills']))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur lors de la mise à jour des scores: {e}")
            return False

    def process_kill_event(self, event):
        print(f"Processing kill event: {event}")
        try:
            if "event" in event:
                event_type = event.get('event', '')
                player_name = None
                if "player" in event and isinstance(event["player"], dict):
                    player_name = event["player"].get("name")
                if not player_name:
                    killer = event.get("data", {}).get("killer")
                    if isinstance(killer, dict):
                        player_name = killer.get("name")
                if not player_name or player_name.lower() in ["self", "null", ""]:
                    print("Aucun joueur valide trouvé dans l'événement LJSON")
                    return False
                if "ANIMAL_DEATH" in event_type:
                    print(f"Animal kill detected by {player_name}")
                    return self.update_player_score(player_name, 'animal')
                elif "INFECTED_DEATH" in event_type:
                    print(f"Zombie kill detected by {player_name}")
                    return self.update_player_score(player_name, 'zombie')
                elif "PLAYER_DEATH" in event_type:
                    print(f"Player kill detected by {player_name}")
                    return self.update_player_score(player_name, 'survivor')
            event_type = event.get('type', '')
            if event_type == 'kill':
                killer = event.get('killer', '')
                match = re.search(r'Player "([^"]+)"', killer)
                if match:
                    player_name = match.group(1)
                    print(f"Player kill detected: {player_name} killed a survivor")
                    return self.update_player_score(player_name, 'survivor')
            elif event_type == 'suicide':
                player = event.get('player', '')
                print(f"Suicide detected for {player}")
                return True
            elif event_type == 'animal_kill':
                player = event.get('player', '')
                print(f"Animal kill detected by {player}")
                return self.update_player_score(player, 'animal')
            elif event_type == 'zombie_kill':
                player = event.get('player', '')
                print(f"Zombie kill detected by {player}")
                return self.update_player_score(player, 'zombie')
        except Exception as e:
            print(f"Error processing kill event: {e}")
            import traceback
            traceback.print_exc()
        return False

# Fonctions pour intégrer avec le bot Discord
def register_commands(bot):
    """Enregistrer les commandes du killboard sur le bot"""
    
    killboard_manager = KillboardManager()
    
    @bot.command()
    async def killboard(ctx, limit: int = 10):
        """Affiche un tableau des scores avec un champion mis en valeur"""
        try:
            top_players = killboard_manager.get_top_players(limit)
    
            if not top_players:
                await ctx.send("❌ Aucun score enregistré pour le moment.")
                return

            embed = discord.Embed(
                title="☢️ TABLEAU DES SCORES ☢️",
                description="*Les chasseurs les plus mortels de la Zone*",
                color=discord.Color.from_rgb(30, 30, 30)
            )

            barème = (
                "◉ SURVIVANT +5 | ◉ AI +4\n"
                "◉ ANIMAL +2   | ◉ ZOMBIE +1\n"
            )
            embed.add_field(name="💀 SYSTÈME DE POINTS", value=barème, inline=False)

            # ⚡ Champion de la Zone
            top_player = top_players[0]
            champion_name = top_player[0].upper()
            champion_points = top_player[1]
            embed.add_field(
                name="👑 CHAMPION DE LA ZONE",
                value=f"🔥 **{champion_name}** avec **{champion_points} points** !",
                inline=False
            )

        # Tableau propre avec padding
            scores_text = "`#  | CHASSEUR       | SCR  | 👤   | 🤖   | 🐺   | 🧟   `\n"

            for i, (player, total, surv, ai, animal, zombie) in enumerate(top_players, 1):
                rank = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i:<2}"

                name_display = player.upper() if i == 1 else player
                name_display = (name_display[:14] + "..") if len(name_display) > 16 else name_display
                name_display = name_display.ljust(14)

                scores_text += (
                    f"`{rank} | {name_display} | {str(total).ljust(4)} | "
                    f"{str(surv).ljust(4)} | {str(ai).ljust(4)} | {str(animal).ljust(4)} | {str(zombie).ljust(4)}`\n"
                )

            embed.add_field(name="🏆 L'ÉLITE DES SURVIVANTS", value=scores_text, inline=False)

            legend = "**👤 Survivants | 🤖 IA | 🐺 Animaux | 🧟 Zombies**"
            embed.add_field(name="📊 LÉGENDE", value=legend, inline=False)

            current_time = datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
            embed.set_footer(text=f"MISE À JOUR: {current_time} | ZONE DE RADIATION ACTIVE")
            embed.set_thumbnail(url="https://dayzaide.fr/Images_Dayz/BlackMarket.png")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Erreur lors de la récupération du tableau des scores: `{str(e)}`")



    
    @bot.command()
    @commands.has_permissions(administrator=True)
    async def reset_scores(ctx):
        """Réinitialise le tableau des scores (admin seulement)"""
        try:
            if killboard_manager.reset_scores():
                await ctx.send("✅ Le tableau des scores a été réinitialisé avec succès.")
            else:
                await ctx.send("❌ Une erreur s'est produite lors de la réinitialisation des scores.")
        except Exception as e:
            await ctx.send(f"❌ Erreur lors de la réinitialisation des scores: {str(e)}")

    @bot.command()
    async def check_timestamp(ctx):
        """Vérifier le dernier timestamp traité"""
        last_timestamp = get_last_processed_event()
        await ctx.send(f"Dernier timestamp traité: `{last_timestamp or 'Aucun'}`")
    
    # Retourner le gestionnaire pour qu'il puisse être utilisé ailleurs dans le bot
    return killboard_manager
