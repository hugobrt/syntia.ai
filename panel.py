import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta

# ====================================================
# 1. ÉTAPE 2 : CONFIGURATION DU BOUTON (APRES LE MODAL)
# ====================================================

# --- A. SÉLECTEUR DE RÔLE (Le menu déroulant que tu voulais) ---
class RoleSelectorView(discord.ui.View):
    def __init__(self, embed, btn_label, target_channel):
        super().__init__(timeout=60)
        self.embed = embed
        self.btn_label = btn_label
        self.target_channel = target_channel

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Choisis le rôle à donner...")
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        
        # Création du bouton final
        view = discord.ui.View(timeout=None)
        custom_id = f"act:role:{role.id}" # On stocke l'ID automatiquement
        view.add_item(discord.ui.Button(label=self.btn_label, style=discord.ButtonStyle.success, custom_id=custom_id, emoji="✅"))
        
        await self.target_channel.send(embed=self.embed, view=view)
        await interaction.response.edit_message(content=f"✅ **Succès !** Embed envoyé avec le bouton pour le rôle {role.mention}.", view=None, embed=None)

# --- B. MODAL POUR LIEN OU MESSAGE (Si pas rôle) ---
class ButtonDetailsModal(discord.ui.Modal):
    def __init__(self, action_type, embed, btn_label, target_channel):
        super().__init__(title=f"Configuration : {action_type}")
        self.action_type = action_type
        self.embed = embed
        self.btn_label = btn_label
        self.target_channel = target_channel
        
        if action_type == "link":
            self.value_input = discord.ui.TextInput(label="Lien URL (https://...)", placeholder="https://discord.com/...")
        else:
            self.value_input = discord.ui.TextInput(label="Message de réponse", placeholder="Texte à répondre quand on clique...")
        
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.value_input.value
        view = discord.ui.View(timeout=None)
        
        if self.action_type == "link":
            if not val.startswith("http"):
                return await interaction.response.send_message("❌ Le lien doit commencer par http ou https.", ephemeral=True)
            view.add_item(discord.ui.Button(label=self.btn_label, style=discord.ButtonStyle.link, url=val))
        
        elif self.action_type == "msg":
            custom_id = f"act:msg:{val}"
            view.add_item(discord.ui.Button(label=self.btn_label, style=discord.ButtonStyle.primary, custom_id=custom_id, emoji="💬"))

        await self.target_channel.send(embed=self.embed, view=view)
        await interaction.response.send_message("✅ Embed envoyé !", ephemeral=True)

# --- C. CHOIX DU TYPE D'ACTION ---
class ButtonTypeView(discord.ui.View):
    def __init__(self, embed, btn_label, target_channel):
        super().__init__(timeout=60)
        self.embed = embed
        self.btn_label = btn_label
        self.target_channel = target_channel

    @discord.ui.button(label="Donner un Rôle", style=discord.ButtonStyle.success, emoji="🎭")
    async def type_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        # C'est ici qu'on lance le sélecteur de rôle
        await interaction.response.edit_message(content="🎭 **Choisis le rôle dans la liste :**", view=RoleSelectorView(self.embed, self.btn_label, self.target_channel))

    @discord.ui.button(label="Lien URL", style=discord.ButtonStyle.secondary, emoji="🔗")
    async def type_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ButtonDetailsModal("link", self.embed, self.btn_label, self.target_channel))

    @discord.ui.button(label="Réponse Message", style=discord.ButtonStyle.secondary, emoji="💬")
    async def type_msg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ButtonDetailsModal("msg", self.embed, self.btn_label, self.target_channel))

# ====================================================
# 2. ÉTAPE 1 : LE FORMULAIRE EMBED
# ====================================================

class EmbedBuilderModal(discord.ui.Modal, title="🎨 Créateur d'Embed"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel

    titre = discord.ui.TextInput(label="Titre", required=True)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=True)
    couleur = discord.ui.TextInput(label="Couleur Hex", required=False, placeholder="Ex: FF0000", max_length=7)
    image_url = discord.ui.TextInput(label="Image (Lien)", required=False)
    btn_label = discord.ui.TextInput(label="Texte du bouton (Laisser vide si aucun)", required=False, placeholder="Ex: Cliquez ici")

    async def on_submit(self, interaction: discord.Interaction):
        # Construction de l'embed
        c = 0x2b2d31
        if self.couleur.value:
            try: c = int(self.couleur.value.replace("#", "").strip(), 16)
            except: pass
        embed = discord.Embed(title=self.titre.value, description=self.description.value, color=c)
        if self.image_url.value: embed.set_image(url=self.image_url.value)

        # SI PAS DE BOUTON : On envoie direct
        if not self.btn_label.value:
            await self.target_channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Embed envoyé dans {self.target_channel.mention}", ephemeral=True)
        
        # SI BOUTON : On demande "Quel type ?"
        else:
            await interaction.response.send_message(
                f"⚙️ **Configuration du bouton :** '{self.btn_label.value}'\nQue doit faire ce bouton ?", 
                view=ButtonTypeView(embed, self.btn_label.value, self.target_channel), 
                ephemeral=True
            )

# ====================================================
# 3. AUTRES FONCTIONS (Warn, Sanction, Selecteurs...)
# ====================================================
# (Code identique à la V4/V5 pour la stabilité)

class SanctionReasonModal(discord.ui.Modal):
    def __init__(self, target_member, action): super().__init__(title=f"{action.capitalize()}"); self.target_member = target_member; self.action = action
    raison = discord.ui.TextInput(label="Raison", required=True)
    duree = discord.ui.TextInput(label="Durée (Timeout uniquement)", placeholder="Minutes", required=False)
    async def on_submit(self, interaction: discord.Interaction):
        try:
            if self.action == "ban": await self.target_member.ban(reason=self.raison.value); m="🔨 Banni."
            elif self.action == "kick": await self.target_member.kick(reason=self.raison.value); m="🦶 Kick."
            elif self.action == "warn": 
                try: await self.target_member.send(f"⚠️ Warn: {self.raison.value}"); m="📢 Warn envoyé."
                except: m="📢 Warn noté (MP fermés)."
            elif self.action == "timeout": await self.target_member.timeout(timedelta(minutes=int(self.duree.value)), reason=self.raison.value); m="⏳ Timeout."
            await interaction.response.send_message(m, ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"❌ Erreur: {e}", ephemeral=True)

class UserSelectView(discord.ui.View):
    def __init__(self, action): super().__init__(timeout=60); self.action = action
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Rechercher le membre...")
    async def select_user(self, i: discord.Interaction, s: discord.ui.UserSelect): await i.response.send_modal(SanctionReasonModal(s.values[0], self.action))

class PollModal(discord.ui.Modal, title="Sondage"):
    def __init__(self, c): super().__init__(); self.c=c
    q = discord.ui.TextInput(label="Question")
    async def on_submit(self, i): 
        m = await self.c.send(embed=discord.Embed(title="📊 Sondage", description=f"### {self.q.value}", color=0xFFD700)); 
        await m.add_reaction("✅"); await m.add_reaction("❌"); await i.response.send_message("✅", ephemeral=True)

class ClearModal(discord.ui.Modal, title="Clear"):
    def __init__(self, c): super().__init__(); self.c=c
    n = discord.ui.TextInput(label="Nombre")
    async def on_submit(self, i): await i.response.defer(ephemeral=True); d=await self.c.purge(limit=int(self.n.value)); await i.followup.send(f"✅ {len(d)} supprimés.", ephemeral=True)

class ChannelSelectView(discord.ui.View):
    def __init__(self, act): super().__init__(timeout=60); self.act = act
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Choisis le salon...")
    async def select_channel(self, i: discord.Interaction, s: discord.ui.ChannelSelect):
        c = i.guild.get_channel(s.values[0].id)
        if not c: return
        if self.act == "embed": await i.response.send_modal(EmbedBuilderModal(c))
        elif self.act == "poll": await i.response.send_modal(PollModal(c))
        elif self.act == "clear": await i.response.send_modal(ClearModal(c))
        elif self.act == "lock": 
            ov = c.overwrites_for(i.guild.default_role); ov.send_messages = not ov.send_messages
            await c.set_permissions(i.guild.default_role, overwrite=ov); await i.response.send_message(f"🔒 État changé: {c.mention}", ephemeral=True)

# ====================================================
# 4. PANEL & LOGIQUE (LISTENER)
# ====================================================

class AdminPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Embed + Bouton", style=discord.ButtonStyle.primary, custom_id="pnl:emb", row=0, emoji="✨")
    async def b_emb(self, i, b): await i.response.send_message("📍 Où ?", view=ChannelSelectView("embed"), ephemeral=True)
    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.success, custom_id="pnl:poll", row=0, emoji="📊")
    async def b_poll(self, i, b): await i.response.send_message("📍 Où ?", view=ChannelSelectView("poll"), ephemeral=True)
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, custom_id="pnl:clr", row=1, emoji="🧹")
    async def b_clr(self, i, b): await i.response.send_message("📍 Où ?", view=ChannelSelectView("clear"), ephemeral=True)
    @discord.ui.button(label="Lock/Unlock", style=discord.ButtonStyle.secondary, custom_id="pnl:lck", row=1, emoji="🔒")
    async def b_lck(self, i, b): await i.response.send_message("📍 Où ?", view=ChannelSelectView("lock"), ephemeral=True)
    
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.primary, custom_id="pnl:warn", row=2, emoji="⚠️")
    async def b_warn(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSelectView("warn"), ephemeral=True)
    @discord.ui.button(label="Timeout", style=discord.ButtonStyle.danger, custom_id="pnl:mute", row=2, emoji="⏳")
    async def b_mute(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSelectView("timeout"), ephemeral=True)
    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, custom_id="pnl:kick", row=2, emoji="🦶")
    async def b_kick(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSelectView("kick"), ephemeral=True)
    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, custom_id="pnl:ban", row=2, emoji="🔨")
    async def b_ban(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSelectView("ban"), ephemeral=True)

class AdminPanel(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(AdminPanelView())
        print("✨ Panel V6 (Sélecteur de Rôle) Actif !")

    # --- ECOUTEUR DES CLICS UTILISATEURS SUR LES BOUTONS CRÉÉS ---
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component: return
        cid = interaction.data.get("custom_id", "")

        # 1. Gestion des Rôles (act:role:ID)
        if cid.startswith("act:role:"):
            try:
                role_id = int(cid.split(":")[2])
                role = interaction.guild.get_role(role_id)
                if not role: return await interaction.response.send_message("❌ Rôle introuvable.", ephemeral=True)
                
                if role in interaction.user.roles:
                    await interaction.user.remove_roles(role)
                    await interaction.response.send_message(f"➖ Rôle {role.mention} retiré.", ephemeral=True)
                else:
                    if role.position >= interaction.guild.me.top_role.position:
                         return await interaction.response.send_message("❌ Je ne peux pas donner ce rôle (il est trop haut pour moi).", ephemeral=True)
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message(f"➕ Rôle {role.mention} ajouté !", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

        # 2. Gestion des Messages (act:msg:TEXTE)
        elif cid.startswith("act:msg:"):
            msg_content = cid.split(":", 2)[2]
            await interaction.response.send_message(msg_content, ephemeral=True)

    @app_commands.command(name="setup_panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction):
        await interaction.channel.send(embed=discord.Embed(title="🎛️ Command Center V6", color=0x2b2d31), view=AdminPanelView())
        await interaction.response.send_message("✅ Panel installé.", ephemeral=True)

async def setup(bot): await bot.add_cog(AdminPanel(bot))
