import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta

from ljson_parser import find_latest_ljson_log, read_ljson_events, format_event_data

# Classe pour gérer les commandes liées aux logs LJSON
class LJSONCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logs_channel_id = 1200564833054101554  # ID du salon pour les logs détaillés
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reset_ljson(self, ctx):
        """Réinitialise la position de lecture des fichiers LJSON (Admin uniquement)"""
        from bot import last_ljson_position
        global last_ljson_position
        last_ljson_position = 0
        await ctx.send("✅ Position de lecture des logs LJSON réinitialisée.")
    
    @commands.command()
    async def ljson_status(self, ctx):
        """Affiche le statut du système de logs LJSON"""
        from bot import last_ljson_position, current_ljson_file
        
        # Trouver le fichier LJSON actuel
        current_file = current_ljson_file
        if not current_file:
            current_file = find_latest_ljson_log()
        
        if not current_file:
            await ctx.send("❌ Aucun fichier de logs LJSON trouvé.")
            return
        
        # Récupérer les informations sur le fichier
        file_size = os.path.getsize(current_file)
        file_modified = datetime.fromtimestamp(os.path.getmtime(current_file))
        read_percentage = (last_ljson_position / file_size) * 100 if file_size > 0 else 0
        
        embed = discord.Embed(
            title="📊 Statut du système de logs LJSON",
            description="Informations sur le système de surveillance des logs",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="📁 Fichier actuel", value=f"{os.path.basename(current_file)}", inline=False)
        embed.add_field(name="📏 Taille du fichier", value=f"{file_size:,} octets", inline=True)
        embed.add_field(name="📍 Position de lecture", value=f"{last_ljson_position:,} octets ({read_percentage:.1f}%)", inline=True)
        embed.add_field(name="🕒 Dernière modification", value=f"{file_modified.strftime('%d/%m/%Y à %H:%M:%S')}", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command()
    async def ljson_filter(self, ctx, event_type="ALL", limit: int = 10):
        """Affiche les logs filtrés par type d'événement
        
        Exemples:
          !ljson_filter PLAYER_DEATH 5
          !ljson_filter ANIMAL_DEATH 3
          !ljson_filter PLAYER 10
        """
        if limit > 20:
            limit = 20  # Limiter à 20 événements maximum
        
        # Trouver le fichier LJSON actuel
        ljson_file = find_latest_ljson_log()
        if not ljson_file:
            await ctx.send("❌ Aucun fichier de logs LJSON trouvé.")
            return
        
        await ctx.send(f"🔍 Recherche des événements de type `{event_type}`...")
        
        # Lire tous les événements (sans mettre à jour la position)
        events, _ = read_ljson_events(ljson_file, 0)
        
        if not events:
            await ctx.send("❌ Aucun événement trouvé dans les logs.")
            return
        
        # Filtrer par type d'événement si spécifié
        if event_type != "ALL":
            filtered_events = [e for e in events if event_type in e.get("event", "")]
        else:
            filtered_events = events
        
        # Prendre les X derniers
        recent = filtered_events[-limit:]
        
        if not recent:
            await ctx.send(f"❌ Aucun événement de type '{event_type}' trouvé.")
            return
        
        # Afficher les événements
        await self.display_events(ctx.channel, recent, f"📋 Logs filtrés - {event_type}")
    
    @commands.command()
    async def ljson_player(self, ctx, player_name, limit: int = 10):
        """Affiche les logs concernant un joueur spécifique
        
        Exemples:
          !ljson_player PlayerName 5
        """
        if limit > 20:
            limit = 20
        
        # Trouver le fichier LJSON actuel
        ljson_file = find_latest_ljson_log()
        if not ljson_file:
            await ctx.send("❌ Aucun fichier de logs LJSON trouvé.")
            return
        
        await ctx.send(f"🔍 Recherche des événements pour le joueur `{player_name}`...")
        
        # Lire tous les événements (sans mettre à jour la position)
        events, _ = read_ljson_events(ljson_file, 0)
        
        if not events:
            await ctx.send("❌ Aucun événement trouvé dans les logs.")
            return
        
        # Filtrer par joueur
        player_events = []
        for event in events:
            # Vérifier dans les données (qui peuvent être une chaîne JSON)
            data = event.get("data", {})
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except:
                    data = {}
            
            # Vérifier dans le joueur
            player_info = event.get("player", {})
            
            # Essayer de trouver le joueur dans différents endroits
            found = False
            
            # Dans l'objet player
            if isinstance(player_info, dict) and player_info.get("name") == player_name:
                found = True
            
            # Dans les données
            if isinstance(data, dict):
                # Dans killer
                killer = data.get("killer", {})
                if (isinstance(killer, dict) and killer.get("name") == player_name) or \
                   (isinstance(killer, str) and player_name in killer):
                    found = True
                
                # Dans target
                target = data.get("target", {})
                if (isinstance(target, dict) and target.get("name") == player_name) or \
                   (isinstance(target, str) and player_name in target):
                    found = True
            
            if found:
                player_events.append(event)
        
        # Prendre les X derniers
        recent = player_events[-limit:]
        
        if not recent:
            await ctx.send(f"❌ Aucun événement trouvé pour le joueur '{player_name}'.")
            return
        
        # Afficher les événements
        await self.display_events(ctx.channel, recent, f"📋 Logs du joueur - {player_name}")
    
    async def display_events(self, channel, events, title):
        """Affiche les événements dans le canal spécifié
        
        Args:
            channel: Canal Discord où envoyer l'embed
            events: Liste des événements à afficher
            title: Titre de l'embed
        """
        if not events:
            await channel.send("❌ Aucun événement à afficher.")
            return
        
        # Trier les événements par timestamp
        events.sort(key=lambda e: e.get("ts", ""))
        
        # Créer l'embed
        embed = discord.Embed(
            title=title,
            description=f"Nombre d'événements: {len(events)}",
            color=discord.Color.blue()
        )
        
        # Ajouter chaque événement
        for event in events:
            event_type = event.get("event", "INCONNU")
            ts = event.get("ts", "")
            data = event.get("data", {})
            
            # Formater les données selon le type d'événement
            content = format_event_data(event_type, data)
            
            # Limiter la taille du contenu pour l'embed
            if len(content) > 1024:
                content = content[:1020] + "..."
            
            embed.add_field(
                name=f"{ts} - {event_type}",
                value=content,
                inline=False
            )
        
        await channel.send(embed=embed)
    
    async def send_event_embed(self, channel, title, events, color_name="blue"):
        """Envoie un embed avec les événements spécifiés
        
        Args:
            channel: Canal Discord où envoyer l'embed
            title: Titre de l'embed
            events: Liste des événements à afficher
            color_name: Nom de la couleur à utiliser
        """
        colors = {
            "blue": discord.Color.blue(),
            "red": discord.Color.red(),
            "green": discord.Color.green(),
            "gold": discord.Color.gold(),
            "purple": discord.Color.purple()
        }
        
        embed = discord.Embed(
            title=title,
            description=f"Derniers événements ({len(events)})",
            color=colors.get(color_name, discord.Color.default())
        )
        
        for event in events:
            event_type = event.get("event", "INCONNU")
            ts = event.get("ts", "")
            data = event.get("data", {})
            
            # Formater les données selon le type d'événement
            content = format_event_data(event_type, data)
            
            # Limiter la taille pour l'embed
            if len(content) > 1024:
                content = content[:1020] + "..."
            
            embed.add_field(
                name=f"{ts} - {event_type}",
                value=content,
                inline=False
            )
        
        await channel.send(embed=embed)
    
    async def display_detailed_logs(self, events):
        """Affiche les événements de logs détaillés dans le salon spécifié
        
        Args:
            events: Liste des événements à afficher
        """
        if not events:
            return
        
        # Obtenir le salon
        channel = self.bot.get_channel(self.logs_channel_id)
        if not channel:
            print(f"Salon de logs détaillés non trouvé: {self.logs_channel_id}")
            return
        
        # Filtrer les événements par type
        player_events = []
        combat_events = []
        kill_events = []
        item_events = []
        vehicle_events = []
        build_events = []
        
        for event in events:
            event_type = event.get("event", "")
            
            if "KILL" in event_type or "DEATH" in event_type or "LETHAL_DAMAGE" in event_type:
                kill_events.append(event)
            elif "PLAYER_" in event_type and "DAMAGE" not in event_type and "DEATH" not in event_type:
                player_events.append(event)
            elif any(x in event_type for x in ["DAMAGE", "HIT"]):
                combat_events.append(event)
            elif any(x in event_type for x in ["ITEM_", "CRAFT"]):
                item_events.append(event)
            elif "VEHICLE" in event_type:
                vehicle_events.append(event)
            elif "BASEBUILDING" in event_type:
                build_events.append(event)
        
        # Envoyer des embeds pour chaque catégorie si des nouveaux événements existent
        if kill_events:
            await self.send_event_embed(channel, "☠️ Morts et Kills", kill_events[-5:], "red")
        
        if player_events:
            await self.send_event_embed(channel, "👤 Activités des Joueurs", player_events[-5:], "blue")
        
        if combat_events:
            await self.send_event_embed(channel, "⚔️ Combats", combat_events[-5:], "gold")
        
        if item_events:
            await self.send_event_embed(channel, "🎒 Objets", item_events[-5:], "green")
        
        if vehicle_events:
            await self.send_event_embed(channel, "🚗 Véhicules", vehicle_events[-5:], "purple")
        
        if build_events:
            await self.send_event_embed(channel, "🔨 Construction", build_events[-5:], "blue")

# Configuration pour ajouter ce Cog au bot
def setup(bot):
    bot.add_cog(LJSONCommands(bot))
