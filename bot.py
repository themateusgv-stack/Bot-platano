import discord
from discord.ext import commands, tasks
import re
import time
from datetime import timedelta
import threading
from flask import Flask
import edge_tts
import os
from PIL import Image, ImageDraw, ImageOps, ImageFont
import io
import requests
import asyncio
import base64
import yt_dlp
import sqlite3
import random
import static_ffmpeg


DOWNLOAD_DIR = "/tmp/bot_audio"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
static_ffmpeg.add_paths()

# --- CONFIGURACIÓN DE FLASK (Servidor Web para Render / Mantener Vivo) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot está vivo!",200

@app.route('/status')
def status():
    return "OK"

# --- CONFIGURACIÓN DEL BOT ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Habilitado para detectar nuevos miembros
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 🔒 SEGURIDAD Y DEPURACIÓN
palabras_prohibidas = ["dox", "doxeo", "raid", "raideo"]
link_regex = r"(https?://\S+|discord.gg/\S+)"
usuarios_mensajes = {}
invitaciones_cache = {}

# 🎮 TORNEOS
TORNEOS = {
    "java": {"nombre": "Java PvP Pro", "activo": True, "jugadores": []},
    "bedrock": {"nombre": "Bedrock Survival", "activo": True, "jugadores": []}
}

CLANES = {
    "clan_1": {
        "nombre": "Clan Alpha ⚔️",
        "descripcion": "...",
        "rol_id": 1509422802128605246,
        "logo": "🛡️"
    },
    "clan_2": {
        "nombre": "clan Beta 👥",
        "descripcion": "...",
        "rol_id": 1509422898396270642,
        "logo": "🦅"
    },
    "clan_3": {
        "nombre": "Clan X 🔥",
        "descripcion": "...",
        "rol_id": 1509422961625530408,
        "logo": "🔥"
    }
}

TIENDA_ROLES = {
    "vip": {
        "nombre": "Rango VIP ✨",
        "precio": 500,
        "rol_id": 1111111111111111111,
        "descripcion": "Acceso a canales exclusivos, canales de voz premium y un color especial en el chat."
    },
    "elite": {
        "nombre": "Rango Élite 👑",
        "precio": 1000,
        "rol_id": 222222222222222222222,
        "descripcion": "Todos los beneficios VIP + prioridad en torneos y permisos para usar comandos TTS especiales."
    },
    "Acceso_a_torneos": {
        "nombre": "Torneos",
        "precio": 1000,
        "rol_id": 3333333333333333,
        "descripcion": "Acceso a la sección de torneos."
    },
    "Acceso_a_clanes": {
        "nombre": "Clanes",
        "precio": 1000,
        "rol_id": 44444444444444444444,
        "descripcion": "Acceso a la sección de clanes."
    },
    "sorteo": {
        "nombre": "Inscripción sorteo Premium 🎟️",
        "precio": 2000,
        "rol_id": 0,
        "descripcion": "Participación activa en un sorteo gigante."
    }
}

salas_dinamicas = []

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'outtmpl': '/tmp/%(id)s.%(ext)s',
    'noplaylist': True,
    'nocheckcertificate': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'scsearch1', 
    'source_address': '0.0.0.0',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'keepvideo': False,
}

FFMPEG_LOCAL_OPTIONS = {
    'options': '-vn',
}

FFMPEG_STREAM_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

def inicializar_db():
    conn = sqlite3.connect("economia_qaybio.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id TEXT PRIMARY KEY,
            monedas INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

inicializar_db()

MENSAJES_PROMO = [
    "🔥 ¡Promociones nuevas en nuestra página! No te las pierdas.",
    "🎁 Únete a la página hoy y reclama tus puntos en el servidor.",
    "🛒 ¡Aprovecha! Compra productos exclusivos por mil puntos.",
    "🚀 Qaybio se actualiza constantemente, visítanos para ver las novedades."
]

ID_CANAL_PROMOCIONES = 1523179944077819984
ID_CANAL_ANUNCIO_COMPRAS = 122321331111111111
ID_CANAL_INVITACIONES = 223231322222222222222222
Precio_sorteo = 2000
ID_canal_LOGS_sorteo = 1111111111
ID_CANAL_PANEL_VOZ = 1537561694325309440

async def cargar_invitaciones():
    """Cargar todas las invitaciones del caché"""
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invitaciones_cache[guild.id] = {invite.code: invite.uses for invite in invites}
        except discord.Forbidden:
            print(f"⚠️ No tengo permisos suficientes para leer invitaciones: {guild.name}")
        except Exception as e:
            print(f"❌ Error al cargar las invitaciones: {e}")

@tasks.loop(hours=3)
async def promocion_diaria():
    canal = bot.get_channel(ID_CANAL_PROMOCIONES)
    if canal:
        mensaje_elegido = random.choice(MENSAJES_PROMO)

        embed = discord.Embed(
            title="🌐 ¡Visita Qaybio!",
            description=f"{mensaje_elegido}\n\n"
                        f"👉 Entra aquí para ganar **50 monedas**: [Ir a Qaybio](https://tiendavirtual-801x.onrender.com/)\n"
                        f"Escribe el comando `!link` y te enviaré tu enlace único por mensaje privado.",
            color=discord.Color.gold()
        )
        URL_DEL_BANNER = "https://tiendavirtual-801x.onrender.com/static/imagenes/banner.jpg"
        embed.set_image(url=URL_DEL_BANNER)
        await canal.send(embed=embed)

@tasks.loop(hours=24)
async def recompensa_mensual_autonoma():
    import datetime
    ahora = datetime.datetime.now()

    conn = sqlite3.connect("economia_qaybio.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS control_premios (
            clave TEXT PRIMARY KEY,
            valor TEXT           
        )
    """)
    conn.commit()

    cursor.execute("SELECT valor FROM control_premios WHERE clave = 'ultimo_mes_premiado'")
    resultado = cursor.fetchone()

    mes_actual_str = ahora.strftime("%Y-%m")

    if resultado is None or resultado[0] != mes_actual_str:
        print(f"📆 [SISTEMA MENSUAL] ¡Ha comenzado un nuevo periodo ({mes_actual_str})! Repartiendo 50 monedas...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios(
                user_id TEXT PRIMARY KEY,
                monedas INTEGER DEFAULT 0           
            )
        """)

        cursor.execute("UPDATE usuarios SET monedas = monedas + 50")

        if resultado is None:
            cursor.execute("INSERT INTO control_premios (clave, valor) VALUES ('ultimo_mes_premiado', ?)", (mes_actual_str,))
        else:
            cursor.execute("UPDATE control_premios SET valor = ? WHERE clave = 'ultimo_mes_premiado'", (mes_actual_str,))

        conn.commit()
        print("💰 [SISTEMA MENSUAL] Se han abonado 50 monedas a todos los usuarios de la base de datos.")

        canal = bot.get_channel(ID_CANAL_ANUNCIO_COMPRAS)
        if canal:
            embed = discord.Embed(
                title="🎁 ¡Llegó tu recompensa mensual!",
                description="Se han depositado **50 monedas** 🪙 automáticamente en las cuentas de todos los usuarios.\n\n"
                            "Revisa tu saldo con `!dinero`.",
                color=discord.Color.green()
            )
            await canal.send(embed=embed)
        
    conn.close()



# --- VISTAS Y MODALES (UI) ---
class FormularioEditarSalaModal(discord.ui.Modal, title="Configurar Sala Temporal"):
    def __init__(self, canal_id: int):
        super().__init__(timeout=None)
        self.canal_id = canal_id

    nombre_input = discord.ui.TextInput(
        label="Nuevo Nombre del Canal",
        placeholder="Ej: Bedrock Realms, Charla...",
        max_length=30,
        required=True
    )

    estado_input = discord.ui.TextInput(
        label="Estado / Descripción (se muestra abajo)",
        placeholder="Ej: Perú es clave, Solo micro...",
        max_length=50,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Evita el timeout de 3 segundos
        await interaction.response.defer(ephemeral=True)

        canal = interaction.guild.get_channel(self.canal_id)
        if not canal:
            return await interaction.followup.send("❌ El canal ya no existe.", ephemeral=True)

        nuevo_nombre = f"🔊 {self.nombre_input.value}"
        nuevo_estado = self.estado_input.value.strip()

        try:
            # Renombrar canal
            await canal.edit(name=nuevo_nombre)

            # Editar el estado de voz (descripción)
            if nuevo_estado:
                try:
                    await interaction.client.http.request(
                        discord.http.Route('PUT', '/channels/{channel_id}/voice-status', channel_id=canal.id),
                        json={'status': nuevo_estado}
                    )
                except Exception as e:
                    print(f"⚠️ Error al actualizar estado de voz: {e}")

            await interaction.followup.send(f"✅ ¡Canal actualizado a **{nuevo_nombre}**!", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("❌ El bot no tiene permisos para editar este canal.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error al editar: `{e}`", ephemeral=True)
            
class ControlSalaView(discord.ui.View):
    def __init__(self, canal_id: int):
        super().__init__(timeout=None)
        self.canal_id = canal_id

    @discord.ui.button(label="Personalizar Sala ✏️", style=discord.ButtonStyle.primary, custom_id="btn_editar_sala_temp")
    async def abrir_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FormularioEditarSalaModal(canal_id=self.canal_id))

class RegistroSorteoModal(discord.ui.Modal, title="Inscripción del Sorteo Premium"):
    nombre_real = discord.ui.TextInput(
        label="Nombre del usuario",
        placeholder="Ej: PlatanoJugador99",
        min_length=3,
        max_length=50,
        required=True
    )
    comentarios = discord.ui.TextInput(
        label="¿Algún mensaje o dato extra para el dueño?",
        style=discord.TextStyle.long,
        placeholder="Escribe aquí cualquier detalle opcional...",
        required=False,
        max_length=200
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        conn = sqlite3.connect("economia_qaybio.db")
        cursor = conn.cursor()

        cursor.execute("SELECT monedas FROM usuarios WHERE user_id=?", (user_id,))
        resultado = cursor.fetchone()
        monedas_actuales = resultado[0] if resultado else 0

        if monedas_actuales < Precio_sorteo:
            conn.close()
            return await interaction.response.send_message(
                f"❌ Inscripción cancelada. Ya no cuentas con las **{Precio_sorteo}** monedas necesarias (Tienes: {monedas_actuales} 🪙).",
                ephemeral=True
            )
        
        try:
            cursor.execute("UPDATE usuarios SET monedas = monedas - ? WHERE user_id = ?", (Precio_sorteo, user_id))
            conn.commit()
        except Exception as e:
            conn.close()
            print(f"Error en la base de datos al comprar sorteo: {e}")
            return await interaction.response.send_message("❌ Ocurrió un error al intentar procesar el pago. Inténtalo de nuevo.", ephemeral=True)
        
        conn.close()

        canal_privado = interaction.guild.get_channel(ID_canal_LOGS_sorteo)
        if canal_privado:
            embed_log = discord.Embed(
                title="🎟️ Nueva inscripción recibida",
                description=f"El usuario {interaction.user.mention} se ha inscrito exitosamente al cobrarle las monedas.",
                color=discord.Color.gold()
            )

            embed_log.add_field(name="👤 Usuario Discord", value=f"{interaction.user} (ID: `{interaction.user.id}`)", inline=True)
            embed_log.add_field(name="📛 Nombre Registrado", value=self.nombre_real.value, inline=True)
            embed_log.add_field(name="💬 Mensaje/Comentario", value=self.comentarios.value or "*Ninguno*", inline=False)
            embed_log.add_field(name="💰 Transacción", value=f"Se descontaron **{Precio_sorteo}** monedas de tu saldo.", inline=False)
            embed_log.set_thumbnail(url=interaction.user.display_avatar.url)

            await canal_privado.send(embed=embed_log)

        canal_anuncios = interaction.guild.get_channel(ID_CANAL_ANUNCIO_COMPRAS)
        if canal_anuncios:
            embed_anuncio_publico = discord.Embed(
                title="🎟️ ¡Nuevo Participante en Sorteo PREMIUM! 🎟️",
                description=f"{interaction.user.mention} ha gastado **{Precio_sorteo}** monedas.",
                color=discord.Color.red()
            )

            embed_anuncio_publico.set_thumbnail(url=interaction.user.display_avatar.url)
            embed_anuncio_publico.set_footer(text="¡Aún hay cupos disponibles!, haz tu compra antes de que terminen.")

            await canal_anuncios.send(embed=embed_anuncio_publico)

        embed_usuario = discord.Embed(
            title="✅ ¡Inscripción completada!",
            description=f"Has pagado **{Precio_sorteo}** monedas 🪙 y tus datos se registraron correctamente.\n"
                        f"¡Mucha suerte en el sorteo!",
            color=discord.Color.green()
        )

        embed_usuario.add_field(name="📛 Registrado como:", value=self.nombre_real.value, inline=True)
        embed_usuario.add_field(name="💳 Nuevo saldo", value=f"{monedas_actuales - Precio_sorteo} 🪙", inline=True)

        await interaction.response.send_message(embed=embed_usuario, ephemeral=True)

class SorteoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Inscribirse al sorteo (2,000 🪙)", style=discord.ButtonStyle.danger, emoji="🎟️", custom_id="btn_inscripcion_sorteo")
    async def inscribirse(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)

        conn = sqlite3.connect("economia_qaybio.db")
        cursor = conn.cursor()
        cursor.execute("SELECT monedas FROM usuarios WHERE user_id = ?", (user_id,))
        resultado = cursor.fetchone()
        conn.close()

        monedas = resultado[0] if resultado else 0

        if monedas < Precio_sorteo:
            return await interaction.response.send_message(
                f"❌ No tienes suficientes monedas para inscribirte.\n"
                f"El costo es de **{Precio_sorteo}** 🪙 y tú tienes **{monedas}** 🪙.\n"
                f"¡Apoya visitando nuestra web para conseguir más!",
                ephemeral=True
            )
        
        await interaction.response.send_modal(RegistroSorteoModal())

class TorneoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Java PvP Pro", style=discord.ButtonStyle.primary)
    async def java(self, interaction: discord.Interaction, button: discord.ui.Button):
        torneo = TORNEOS["java"]
        if not torneo["activo"]:
            return await interaction.response.send_message("🔒 Torneo cerrado.", ephemeral=True)
        if interaction.user.name in torneo["jugadores"]:
            return await interaction.response.send_message("⚠️ Ya estás registrado.", ephemeral=True)
        
        torneo["jugadores"].append(interaction.user.name)
        await interaction.response.send_message(f"✅ Te registraste en {torneo['nombre']}", ephemeral=True)

    @discord.ui.button(label="Bedrock Survival", style=discord.ButtonStyle.success)
    async def bedrock(self, interaction: discord.Interaction, button: discord.ui.Button):
        torneo = TORNEOS["bedrock"]
        if not torneo["activo"]:
            return await interaction.response.send_message("🔒 Torneo cerrado.", ephemeral=True)
        if interaction.user.name in torneo["jugadores"]:
            return await interaction.response.send_message("⚠️ Ya estás registrado.", ephemeral=True)
        
        torneo["jugadores"].append(interaction.user.name)
        await interaction.response.send_message(f"✅ Te registraste en {torneo['nombre']}", ephemeral=True)

class SeleccionarClanMenu(discord.ui.Select):
    def __init__(self):
        opciones = []
        for clave, datos in CLANES.items():
            opciones.append(discord.SelectOption(
                label=datos["nombre"], 
                value=clave, 
                description=datos["descripcion"][:50],
                emoji=datos["logo"]
            ))
        super().__init__(placeholder="Elige el clan al que deseas unirte...", min_values=1, max_values=1, options=opciones)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        clan_elegido = CLANES[self.values[0]]
        rol = guild.get_role(clan_elegido["rol_id"])

        if not rol:
            return await interaction.response.send_message("❌ Error: El rol de este clan no está configurado correctamente en el bot.", ephemeral=True)

        for clan in CLANES.values():
            if guild.get_role(clan["rol_id"]) in interaction.user.roles:
                return await interaction.response.send_message("⚠️ Ya perteneces a un clan actualmente. Debes salir de tu clan actual primero.", ephemeral=True)

        try:
            await interaction.user.add_roles(rol)
            await interaction.response.send_message(f"🎉 ¡Felicidades! Te has unido exitosamente al clan **{clan_elegido['nombre']}**.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ El bot no tiene permisos jerárquicos suficientes para darte este rol.", ephemeral=True)

class CrearClanModal(discord.ui.Modal, title="Formulario de Creación de Clan"):
    nombre_clan = discord.ui.TextInput(label="Nombre del Clan", placeholder="Ej: Los Imparables", min_length=3, max_length=30)
    desc_clan = discord.ui.TextInput(label="Descripción Breve", style=discord.TextStyle.long, placeholder="Explica de qué trata tu clan y tus objetivos...", min_length=10, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        permisos = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        numero_ticket = 1
        for channel in guild.channels:
            if channel.name.startswith("ticket-clan-"):
                try:
                    num = int(channel.name.split("-")[-1])
                    if num >= numero_ticket:
                        numero_ticket = num + 1
                except ValueError:
                    pass

        canal_ticket = await guild.create_text_channel(
            name=f"ticket-clan-{numero_ticket}",
            overwrites=permisos,
            topic=f"Solicitud de clan de {interaction.user.name}"
        )

        embed_ticket = discord.Embed(
            title=f"📥 Nueva Solicitud de Clan #{numero_ticket}",
            description=f"Hola {interaction.user.mention}, un administrador revisará tu propuesta pronto.",
            color=discord.Color.blue()
        )
        embed_ticket.add_field(name="🏷️ Nombre propuesto", value=self.nombre_clan.value, inline=False)
        embed_ticket.add_field(name="📜 Descripción enviada", value=self.desc_clan.value, inline=False)
        embed_ticket.set_footer(text="⚠️ Por favor, adjunta o envía el enlace del LOGO que deseas usar aquí abajo.")

        await canal_ticket.send(embed=embed_ticket)
        await interaction.response.send_message(f"✅ Solicitud procesada. Se ha creado tu canal privado en: {canal_ticket.mention}", ephemeral=True)

class ClanView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ver Clanes", style=discord.ButtonStyle.primary, emoji="📋")
    async def ver_clanes(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        embed = discord.Embed(
            title="🛡️ Registro General de Clanes",
            description="Aquí tienes la lista completa de las facciones activas en el servidor:",
            color=discord.Color.gold()
        )

        for clave, datos in CLANES.items():
            rol = guild.get_role(datos["rol_id"])
            num_miembros = len(rol.members) if rol else 0
            
            info_clan = f"**Logo:** {datos['logo']}\n**Miembros actuales:** `{num_miembros}`\n**Descripción:** {datos['descripcion']}"
            embed.add_field(name=f"🔹 {datos['nombre']}", value=info_clan, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Unirse a un Clan", style=discord.ButtonStyle.success, emoji="⚔️")
    async def unirse_clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        vista_menu = discord.ui.View()
        vista_menu.add_item(SeleccionarClanMenu())
        await interaction.response.send_message("Selecciona el clan al que deseas ingresar:", view=vista_menu, ephemeral=True)

    @discord.ui.button(label="Crear Clan", style=discord.ButtonStyle.secondary, emoji="👑")
    async def crear_clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CrearClanModal())

    @discord.ui.button(label="Salir del Clan", style=discord.ButtonStyle.danger, emoji="🚪")
    async def salir_clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        clanes_removidos = []

        for clan in CLANES.values():
            rol = guild.get_role(clan["rol_id"])
            if rol and rol in interaction.user.roles:
                try:
                    await interaction.user.remove_roles(rol)
                    clanes_removidos.append(clan["nombre"])
                except discord.Forbidden:
                    return await interaction.response.send_message("❌ Error: El bot no tiene permisos jerárquicos para remover tu rol.", ephemeral=True)

        if clanes_removidos:
            nombres_clanes = ", ".join(clanes_removidos)
            await interaction.response.send_message(f"🚪 Has abandonado con éxito el clan: **{nombres_clanes}**. Tu historial y demás roles permanecen intactos.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ No te encuentras registrado en ningún clan de la base de datos.", ephemeral=True)

class consultaModal(discord.ui.Modal, title="Formulario de Consulta"):
    asunto_consulta = discord.ui.TextInput(
        label="Asunto / tema corto",
        placeholder="Ej: Mejoras clan / Duda de evento",
        min_length=5,
        max_length=50
    )
    detalle_consulta = discord.ui.TextInput(
        label="Escribe tu consulta detallada aquí",
        style=discord.TextStyle.long,
        placeholder="Escribe a detalle tu consulta para que el staff pueda ayudarte...",
        min_length=15,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild

        permisos = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        numero_ticket = 1
        for channel in guild.channels:
            if channel.name.startswith("ticket-consulta-"):
                try:
                    num = int(channel.name.split("-")[-1])
                    if num >= numero_ticket:
                        numero_ticket = num + 1
                except ValueError:
                    pass

        canal_ticket = await guild.create_text_channel(
            name=f"ticket-consulta-{numero_ticket}",
            overwrites=permisos,
            topic=f"Consulta privada de {interaction.user.name}"
        )

        embed_soporte = discord.Embed(
            title=f"Consulta de Soporte #{numero_ticket}",
            description=f"Hola {interaction.user.mention}, un miembro del staff atenderá tu consulta lo antes posible.",
            color=discord.Color.green()
        )
        embed_soporte.add_field(name="Asunto", value=self.asunto_consulta.value, inline=False)
        embed_soporte.add_field(name="Detalle de la consulta", value=self.detalle_consulta.value, inline=False)
        embed_soporte.set_footer(text="Plátano-Bot | Sistema de soporte", icon_url=guild.me.display_avatar.url)

        await canal_ticket.send(embed=embed_soporte)
        await interaction.response.send_message(f"¡Tu consulta fue creada! Ve a tu canal privado aquí: {canal_ticket.mention}", ephemeral=True)

class TicketConsultaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Realizar consulta", style=discord.ButtonStyle.success, emoji="💬", custom_id="btn_realizar_consulta")
    async def realizar_consulta(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(consultaModal())

class SalaVozView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Crear Sala Temporal 🔊", style=discord.ButtonStyle.primary, emoji="➕", custom_id="btn_crear_sala_voz_visual")
    async def crear_sala(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        if not member.voice or not member.voice.channel:
            return await interaction.response.send_message(
                "⚠️ **Para crear tu sala debes estar conectado a un canal de voz primero.**\n"
                "Conéctate a cualquier canal de voz e inténtalo de nuevo para moverte automáticamente.",
                ephemeral = True
            )

        nombre_canal = f"🔊 Sala de {interaction.user.display_name}"

        try:
            await interaction.response.defer(ephemeral = True)

            categoria_destino = interaction.channel.category if hasattr(interaction.channel, 'category') else None
            
            nuevo_canal = await guild.create_voice_channel(
                name=nombre_canal,
                category = categoria_destino,
                reason=f"Sala temporal creada por {member.display_name}"
            )
            salas_dinamicas.append(nuevo_canal.id)

            await member.move_to(nuevo_canal, reason="Movimiento automático a su nueva sala de voz temporal.")

            await interaction.followup.send(
                f"✅ ¡Hecho! Te he movido obligatoriamente a tu sala: {nuevo_canal.mention}", 
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message("❌ El bot no tiene permisos para crear canales de voz.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ocurrió un error: {e}", ephemeral=True)

# --- EVENTOS DEL BOT ---
@bot.event
async def on_ready():
    bot.add_view(TicketConsultaView())
    bot.add_view(SalaVozView())
    bot.add_view(SorteoView())

    await cargar_invitaciones()

    canal_panel = bot.get_channel(ID_CANAL_PANEL_VOZ)
    if canal_panel:
        embed_panel = discord.Embed(
            title = "🔊Central de Sala de Voz temporales",
            description = "Presiona el botón **Crear Sala Temporal 🔊** de abajo para abrir una sala privada instantánea.\n\n"
                        "✨ **Reglas automáticas:**\n"
                        "• Tu sala permanecerá mientras haya usuarios dentro.\n"
                        "• **Se borrará automáticamente** cuando la última persona se desconecte.",
            color = discord.Color.blurple()
        )
        embed_panel.set_footer(text= "Platano-Bot • Sistema dinámico de Voz")

        try:
            await canal_panel.send(embed=embed_panel, view=SalaVozView())
            print(f"✅ Panel de salas de voz publicado en el canal #{canal_panel.name}")
        except Exception as e:
            print(f"⚠️ No se pudo enviar el panel de salas de voz: {e}")
            
    print(f"✅ Bot conectado como {bot.user}")
    
    if not promocion_diaria.is_running():
        promocion_diaria.start()
    if not recompensa_mensual_autonoma.is_running():
        recompensa_mensual_autonoma.start()
        
@bot.event
async def on_member_join(member):
    ID_DEL_CANAL = 1509365073166991420
    ID_DEL_ROL = 1509366583968141412

    guild = member.guild
    invitador = None
    codigo_usado = None

    try:
        invitaciones_actuales = await guild.invites()
        cache_servidor = invitaciones_cache.get(guild.id, {})

        for invite in invitaciones_actuales:
            usos_previos = cache_servidor.get(invite.code, 0)
            if invite.uses > usos_previos:
                invitador = invite.inviter
                codigo_usado = invite.code
                break

        invitaciones_cache[guild.id] = {invite.code: invite.uses for invite in invitaciones_actuales}
    
    except discord.Forbidden:
        print("❌ El bot no tiene permisos para gestionar/ver invitaciones ('Manage Server')")
    except Exception as e:
        print(f"❌ Error al procesar invitaciones: {e}")
    
    if invitador and not invitador.bot:
        invitador_id = str(invitador.id)

        conn = sqlite3.connect("economia_qaybio.db")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                user_id TEXT PRIMARY KEY,
                monedas INTEGER DEFAULT 0
            )
        """)

        cursor.execute("SELECT monedas FROM usuarios WHERE user_id = ?", (invitador_id,))
        resultado = cursor.fetchone()

        if resultado:
            cursor.execute("UPDATE usuarios SET monedas = monedas + 10 WHERE user_id = ?", (invitador_id,))
            nuevas_monedas = resultado[0] + 10
        else:
            cursor.execute("INSERT INTO usuarios (user_id, monedas) VALUES (?, 10)", (invitador_id,))
            nuevas_monedas = 10
        
        conn.commit()
        conn.close()

        canal_invites = guild.get_channel(ID_CANAL_INVITACIONES)
        if canal_invites:
            embed_invite = discord.Embed(
                title="📈 ¡Nueva invitación exitosa!",
                description=f"¡El enlace de invitación de {invitador.mention} ha sido utilizado!",
                color=discord.Color.green()
            )
            embed_invite.add_field(name="👤 Invitado", value=member.mention, inline=True)
            embed_invite.add_field(name="👤 Invitado por", value=invitador.mention, inline=True)
            embed_invite.add_field(name="🎟️ Código usado", value=f"+10 monedas 🪙 (Total actual: {nuevas_monedas})", inline=False)
            embed_invite.set_thumbnail(url=member.display_avatar.url)
            embed_invite.set_footer(text="¡Gracias por ayudar a que crezca la comunidad!")

            await canal_invites.send(embed=embed_invite)
    
    role = member.guild.get_role(ID_DEL_ROL)
    if role:
        try:
            await member.add_roles(role)
            print(f"✅ Rol '{role.name}' asignado automáticamente a {member.name}")
        except discord.Forbidden:
            print(f"❌ Error 403: El bot no tiene permisos suficientes. ¿Su rol está por encima de '{role.name}'?")
    else:
        print(f"❌ Error: No se encontró ningún rol con el ID {ID_DEL_ROL} en este servidor.")

    canal_bienvenida = guild.get_channel(ID_DEL_CANAL)
    if canal_bienvenida:
        try:
            archivo_banner = None
            for extension in ["banner.png", "banner.jpg", "banner.jpeg"]:
                if os.path.exists(extension):
                    archivo_banner = extension
                    break

            if archivo_banner:
                background = Image.open(archivo_banner).convert("RGBA")
            else:
                background = Image.new("RGBA", (800, 400), color=(44, 47, 51, 255))
        
            avatar_url = member.display_avatar.url
            response = requests.get(avatar_url)
            avatar_img = Image.open(io.BytesIO(response.content)).convert("RGBA")

            avatar_size = (100, 100)
            avatar_img = avatar_img.resize(avatar_size, Image.Resampling.LANCZOS)

            mascara = Image.new("L", avatar_size, 0)
            draw_mask = ImageDraw.Draw(mascara)
            draw_mask.ellipse((0, 0) + avatar_size, fill=255)

            avatar_circular = ImageOps.fit(avatar_img, avatar_size, centering=(0.5, 0.5))
            avatar_circular.putalpha(mascara)

            posicion_avatar = (160, 100)
            background.paste(avatar_circular, posicion_avatar, avatar_circular)

            draw = ImageDraw.Draw(background)

            color_borde = (255, 204, 0, 255)
            grosor_borde = 4

            x0 = posicion_avatar[0] - grosor_borde // 2
            y0 = posicion_avatar[1] - grosor_borde // 2
            x1 = posicion_avatar[0] + avatar_size[0] + grosor_borde // 2
            y1 = posicion_avatar[1] + avatar_size[1] + grosor_borde // 2

            draw.ellipse([x0, y0, x1, y1], outline=color_borde, width=grosor_borde)

            texto_bienvenida = f"¡Bienvenido, {member.name}!"
            texto_miembro = f"Miembro #{len(guild.members)}"

            try:
                fuente_principal = ImageFont.truetype("BILLO___.TTF", 26)
                fuente_secundaria = ImageFont.truetype("BILLO___.TTF", 28)
            except IOError:
                try:
                    fuente_principal = ImageFont.truetype("impact.ttf", 28)
                    fuente_secundaria = ImageFont.truetype("impact.ttf", 18)
                except IOError:
                    fuente_principal = ImageFont.load_default()
                    fuente_secundaria = ImageFont.load_default()

            pos_x_texto = 70
            draw.text((pos_x_texto, 250), texto_bienvenida, fill=(255, 255, 255, 255), anchor="ls", font=fuente_principal)
            draw.text((100, 285), texto_miembro, fill=(255, 204, 0, 255), anchor="ls", font=fuente_secundaria)

            img_byte_arr = io.BytesIO()
            background.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            archivo_discord = discord.File(fp=img_byte_arr, filename='bienvenida.png')
            mensaje_personalizado = f"¡Hola {member.mention}! Bienvenido a **{guild.name}**"

            await canal_bienvenida.send(content=mensaje_personalizado, file=archivo_discord)

        except Exception as e:
            print(f"Error al generar el banner de bienvenida: {e}")

@bot.event
async def on_invite_create(invite):
    if invite.guild.id not in invitaciones_cache:
        invitaciones_cache[invite.guild.id] = {}
    invitaciones_cache[invite.guild.id][invite.code] = invite.uses

@bot.event
async def on_invite_delete(invite):
    if invite.guild.id in invitaciones_cache:
        invitaciones_cache[invite.guild.id].pop(invite.code, None)

@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel and after.channel.id == ID_CANAL_PANEL_VOZ:
        guild = member.guild
        categoria = after.channel.category
        
        try:
            # 1. Crear canal inmediatamente
            nueva_sala = await guild.create_voice_channel(
                name=f"🔊 Sala de {member.display_name}",
                category=categoria,
                reason="Sala de voz temporal"
            )
            salas_dinamicas.append(nueva_sala.id)

            # 2. Mover al usuario de inmediato sin sacarlo de voz
            await member.move_to(nueva_sala)

            # 3. Mandar el botón al chat integrado de la propia sala creada
            embed = discord.Embed(
                title="🎙️ ¡Bienvenido a tu sala temporal!",
                description="Presiona el botón de abajo si quieres cambiar el **Nombre** o el **Estado** del canal.",
                color=discord.Color.green()
            )
            await nueva_sala.send(embed=embed, view=ControlSalaView(canal_id=nueva_sala.id))

        except discord.Forbidden:
            print("❌ Falta permiso 'Mover Miembros' o 'Administrar Canales'.")
        except Exception as e:
            print(f"❌ Error en la creación de la sala: {e}")
            
    if before.channel and before.channel.id in salas_dinamicas:
        if len(before.channel.members) == 0:
            salas_dinamicas.remove(before.channel.id)
            try:
                await before.channel.delete(reason="Canal temporal vacío")
            except Exception as e:
                print(f"❌ No se pudo eliminar el canal temporal: {e}")

# Manejador Unificado de Mensajes
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    contenido = message.content.lower() if message.content else ""

    # 🛡️ Filtros de Seguridad (Mensajes prohibidos)
    for palabra in palabras_prohibidas:
        if palabra in contenido:
            try:
                await message.delete()
            except:
                pass
            return await message.channel.send(f"{message.author.mention} 🚫 Mensaje prohibido.", delete_after=5)

    # ⏳ Control Antispam
    if not message.author.bot:
        ahora = time.time()
        u_id = message.author.id
        if u_id not in usuarios_mensajes:
            usuarios_mensajes[u_id] = []
        
        usuarios_mensajes[u_id].append(ahora)
        usuarios_mensajes[u_id] = [t for t in usuarios_mensajes[u_id] if ahora - t < 5]

        if len(usuarios_mensajes[u_id]) > 5:
            try:
                await message.author.timeout(timedelta(minutes=10), reason="Spam detectado")
                await message.channel.send(f"🚫 {message.author.mention} ha sido silenciado 10 min por spam.")
            except:
                pass
            return

    # 🕵️‍♂️ Webhook / Sistema de Captura de Recompensas por Click
    contenido_texto = message.content if message.content else ""
    if not contenido_texto and message.embeds:
        for embed in message.embeds:
            if embed.description and "SISTEMA_MONEDAS_RECOMPENSA:" in embed.description:
                contenido_texto = embed.description
                break

    if "SISTEMA_MONEDAS_RECOMPENSA:" in contenido_texto:
        try:
            user_id = contenido_texto.split("SISTEMA_MONEDAS_RECOMPENSA:")[1].strip()
            print(f"\n📥 [¡LISTENER CAPTURADO!] Se detectó clic para el ID: {user_id}")
            
            conn = sqlite3.connect("economia_qaybio.db")
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    user_id TEXT PRIMARY KEY,
                    monedas INTEGER DEFAULT 0
                )
            """)
            
            cursor.execute("SELECT monedas FROM usuarios WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE usuarios SET monedas = monedas + 50 WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("INSERT INTO usuarios (user_id, monedas) VALUES (?, 50)", (user_id,))
                
            conn.commit()
            conn.close()
            
            try:
                usuario_discord = await bot.fetch_user(int(user_id))
                await message.channel.send(f"🪙 ¡Visita confirmada! {usuario_discord.mention} ha recibido **50 monedas** por apoyar a Qaybio.")
            except Exception as e:
                print(f"No se pudo enviar la confirmación en el chat: {e}")
                
            try:
                await message.delete()
            except:
                pass

        except Exception as e:
            print(f"❌ Error interno en el Listener de monedas: {e}")

    # Procesar Comandos
    await bot.process_commands(message)

# --- COMANDOS DEL BOT ---

@bot.command(name="tienda", aliases=["store", "shop"])
async def mostrar_tienda(ctx):
    """Muestra los rangos disponibles para comprar con monedas de Qaybio."""
    embed = discord.Embed(
        title="🛒 Tienda oficial de Rangos",
        description="¡Utiliza tus monedas acumuladas para comprar rangos exclusivos en el servidor!\n\n"
                    "👉 *Para comprar un rango usa:* `!comprar <nombre_rango>`\n*EJEMPLO:* `!comprar vip`",
        color=discord.Color.purple()
    )

    for clave, datos in TIENDA_ROLES.items():
        nombre = datos.get("nombre", clave.upper())
        precio = datos.get("precio", 0)
        descripcion = datos.get("descripcion", "Sin descripción disponible.")

        info_producto = (
            f"**💰 Precio:** {precio} 🪙 monedas\n"
            f"**📜 Beneficios:** {descripcion}\n"
            f"**🔑 Comando de compra:** `!comprar {clave}`"
        )
        embed.add_field(name=f"🔹 {nombre}", value=info_producto, inline=False)

    embed.set_footer(text="Plátano bot • Economía e Interacciones", icon_url=ctx.guild.me.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name="comprar", aliases=["buy", "canjear"])
async def comprar_rango(ctx, rango: str = None):
    """Procesa la compra de un rango descontando las monedas de la base de datos."""
    if not rango:
        return await ctx.send(f"⚠️ {ctx.author.mention}, debes especificar qué rango deseas comprar. Usa `!tienda` para ver las opciones.")
    
    rango = rango.lower()

    if rango not in TIENDA_ROLES:
        return await ctx.send(f"❌ {ctx.author.mention}, el rango `{rango}` no existe en la tienda. Revisa la lista usando `!tienda`.")
    
    producto = TIENDA_ROLES[rango]
    guild = ctx.guild
    rol_recompensa = guild.get_role(producto["rol_id"])

    if not rol_recompensa:
        return await ctx.send("❌ Error de configuración: El rol solicitado no existe o su ID está mal configurado en el código.")
    
    if rol_recompensa in ctx.author.roles:
        return await ctx.send(f"⚠️ {ctx.author.mention}, ¡tú ya posees el rango **{producto['nombre']}**!")
    
    user_id = str(ctx.author.id)

    conn = sqlite3.connect("economia_qaybio.db")
    cursor = conn.cursor()

    cursor.execute("SELECT monedas FROM usuarios WHERE user_id = ?", (user_id,))
    resultado = cursor.fetchone()

    monedas_actuales = resultado[0] if resultado else 0

    if monedas_actuales < producto["precio"]:
        conn.close()
        falta = producto["precio"] - monedas_actuales
        return await ctx.send(f"❌ {ctx.author.mention}, no tienes suficientes monedas. El rango cuesta **{producto['precio']}** y tú tienes **{monedas_actuales}** (te faltan `{falta}` 🪙).")
    
    try:
        cursor.execute("UPDATE usuarios SET monedas = monedas - ? WHERE user_id = ?", (producto["precio"], user_id))
        conn.commit()
    except Exception as e:
        conn.close()
        print(f"Error al descontar monedas en la base de datos: {e}")
        return await ctx.send("❌ Ocurrió un error interno al procesar el pago. Compra cancelada.")
    
    conn.close()

    try:
        await ctx.author.add_roles(rol_recompensa)

        embed_exito = discord.Embed(
            title="🎉 ¡Compra realizada con Éxito!",
            description=f"¡Felicidades {ctx.author.mention}! Has adquirido el rango **{producto['nombre']}**",
            color=discord.Color.green()
        )

        embed_exito.add_field(name="💰 Precio Pagado", value=f"`{producto['precio']}` monedas 🪙", inline=True)
        embed_exito.add_field(name="💳 Saldo Actual", value=f"`{monedas_actuales - producto['precio']}` monedas 🪙", inline=True)
        embed_exito.set_footer(text="¡Disfruta tus nuevos beneficios exclusivos!")

        await ctx.send(embed=embed_exito)

        canal_anuncios = guild.get_channel(ID_CANAL_ANUNCIO_COMPRAS)
        if canal_anuncios:
            embed_anuncio = discord.Embed(
                title="🛍️ ¡Nueva compra en nuestra tienda! 🛍️",
                description=f"¡Atención comunidad! {ctx.author.mention} acaba de canjear sus monedas por un beneficio exclusivo.",
                color=discord.Color.gold()
            )

            embed_anuncio.add_field(name="👤 Comprador", value=ctx.author.mention, inline=True)
            embed_anuncio.add_field(name="✨ Artículo adquirido", value=f"**{producto['nombre']}**", inline=True)
            embed_anuncio.set_thumbnail(url=ctx.author.display_avatar.url)
            embed_anuncio.set_footer(text="¡Sigue sumando monedas visitando nuestra página web! 🪙")

            await canal_anuncios.send(embed=embed_anuncio)

    except discord.Forbidden:
        conn = sqlite3.connect("economia_qaybio.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE usuarios SET monedas = monedas + ? WHERE user_id = ?", (producto["precio"], user_id))
        conn.commit()
        conn.close()

        await ctx.send("❌ El bot no pudo asignarte tu rol por un conflicto de permisos jerárquicos de Discord. Se han reembolsado tus monedas automáticamente.")

@bot.command(name="dinero", aliases=["moneda", "coins"])
async def ver_dinero(ctx, miembro: discord.Member = None):
    """Muestra la cantidad de monedas que tiene un usuario."""
    miembro = miembro or ctx.author
    user_id = str(miembro.id)

    conn = sqlite3.connect("economia_qaybio.db")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                user_id TEXT PRIMARY KEY,
                monedas INTEGER DEFAULT 0
            )
        """)
        conn.commit()

        cursor.execute("SELECT monedas FROM usuarios WHERE user_id = ?", (user_id,))
        resultado = cursor.fetchone()
        
    except sqlite3.Error as e:
        print(f"Error interno de SQLite: {e}")
        resultado = None
    finally:
        conn.close()

    monedas = resultado[0] if resultado else 0

    embed = discord.Embed(
        title="💰 Banco de Qaybio",
        description=f"{miembro.mention} tiene actualmente **{monedas}** 🪙 monedas.",
        color=discord.Color.yellow()
    )
    await ctx.send(embed=embed)

@bot.command(name="link", aliases=["enlace", "web"])
async def enviar_enlace_personal(ctx):
    """Envía el link único por privado para que el clic sume monedas a este usuario específico."""
    user_id = ctx.author.id
    url_monedas = f"https://tiendavirtual-801x.onrender.com/click?user_id={user_id}"
    
    embed = discord.Embed(
        title="🪙 Tu Enlace Personal de Monedas",
        description=f"¡Hola {ctx.author.mention}! Haz clic abajo para visitar Qaybio y reclamar tus **50 monedas**:\n\n"
                    f"🚀 [¡Reclamar mis 50 Monedas Aquí!]({url_monedas})",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Tu ID está enlazado de forma segura.")
    
    try:
        await ctx.author.send(embed=embed)
        await ctx.send(f"📬 {ctx.author.mention}, ¡te envié tu link personalizado por mensaje privado!")
    except discord.Forbidden:
        await ctx.send(f"⚠️ {ctx.author.mention}, no tengo permiso para enviarte mensajes privados. ¡Actívalos en este servidor!")

@bot.command()
async def sala_voz(ctx):
    embed = discord.Embed(
        title="🔊 Canales de Voz Temporales",
        description="¿Necesitas una sala pública para hablar con tus amigos o tu team?\n\nPresiona el botón de abajo para crear una sala al instante. ¡Se borrará sola cuando todos salgan!",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Plátano-Bot • Sistema de Voz")
    
    await ctx.send(embed=embed, view=SalaVozView())
    try:
        await ctx.message.delete()
    except:
        pass

@bot.command()
async def ticket(ctx):
    ticket_channel_id = 1509365435831816432
    if ctx.channel.id != ticket_channel_id:
        await ctx.send("❌ Usa esto en #ticket-consultas")
        return

    embed = discord.Embed(
        title="🎮 Torneos Disponibles",
        description="Haz clic en un botón para registrarte",
        color=discord.Color.orange()
    )
    for torneo in TORNEOS.values():
        if torneo["activo"]:
            embed.add_field(name="Disponible", value=torneo["nombre"], inline=False)

    await ctx.send(embed=embed, view=TorneoView())

@bot.command()
async def soporte(ctx):
    embed = discord.Embed(
        title="⚙️ Centro de Consultas y Soporte Técnico",
        description="¿Tienes alguna duda, reporte o inconveniente con el servidor?\n\nPresiona el botón de **💬 Realizar consulta** aquí abajo para abrir un canal privado y comunicarte directamente con la administración.",
        color=discord.Color.teal()
    )
    embed.set_footer(text="Plátano-Bot • Soporte del Servidor")
    
    await ctx.send(embed=embed, view=TicketConsultaView())
    try:
        await ctx.message.delete()
    except:
        pass

@bot.command()
async def clan(ctx):
    embed = discord.Embed(
        title="🛡️ Sistema de Gestión de Clanes",
        description="Gestiona tu lealtad, visualiza los clanes activos o solicita fundar uno nuevo usando las opciones interactivas de abajo.",
        color=discord.Color.dark_purple()
    )
    embed.set_footer(text="Plátano-Bot • Sistema de Facciones")
    
    await ctx.send(embed=embed, view=ClanView())

@bot.command(name="say", aliases=["tts"])
async def tts_say(ctx, *, texto: str):
    """Convierte texto a voz y lo reproduce en el canal del usuario."""

    if not ctx.author.voice:
        return await ctx.send(f"⚠️ {ctx.author.mention}, ¡debes estar en un canal de voz para usar este comando!")
    
    canal_voz = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not voice_client:
        voice_client = await canal_voz.connect()
    elif voice_client.channel != canal_voz:
        await voice_client.move_to(canal_voz)

    archivo_audio = f"tts_{ctx.guild.id}.mp3"
    musica_pausada = False
    archivo_original_musica = None

    if voice_client.is_playing() and getattr(voice_client, 'is_music', False):
        musica_pausada = True
        archivo_original_musica = getattr(voice_client, 'archivo_musica', None)

        tiempo_reproducido = time.time() - voice_client.inicio_tiempo
        voice_client.segundos_acumulados += tiempo_reproducido

        voice_client.stop()

    try:
        tts = f"{ctx.author.display_name} dice: {texto}"
        communicate = edge_tts.Communicate(tts, "es-AR-ElenaNeural")
        await communicate.save(archivo_audio)

        source_tts = discord.FFmpegPCMAudio(archivo_audio)
        voice_client.is_music = False

        def after_playing(error):
            if os.path.exists(archivo_audio):
                try:
                    os.remove(archivo_audio)
                except:
                    pass
        
            if musica_pausada and archivo_original_musica and os.path.exists(archivo_original_musica):
                voice_client.is_music = True

                opciones_reanudar = {
                    'options': f'-vn -ss {int(voice_client.segundos_acumulados)}'
                }

                source_musica = discord.FFmpegPCMAudio(archivo_original_musica, **opciones_reanudar)
                voice_client.inicio_tiempo = time.time()
                bot.loop.call_soon_threadsafe(voice_client.play, source_musica)

        voice_client.play(source_tts, after=after_playing)
        
    except Exception as e:
        await ctx.send(f"❌ Error al reproducir el TTS: {e}")

@bot.command(name="play", aliases=["p"])
async def play(ctx, *, busqueda: str):
    """Busca en SoundCloud, descarga localmente en /tmp y reproduce audio."""
    if not ctx.author.voice:
        return await ctx.send(f"⚠️ {ctx.author.mention}, ¡debes entrar a un canal de voz primero!")

    canal_voz = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not voice_client:
        voice_client = await canal_voz.connect()
    elif voice_client.channel != canal_voz:
        await voice_client.move_to(canal_voz)

    mensaje_espera = await ctx.send(f"🟠 Buscando **{busqueda}** en SoundCloud...")

    loop = bot.loop or asyncio.get_event_loop()
    try:    
        es_url = busqueda.startswith("http://") or busqueda.startswith("https://")
        
        # Si no es URL, forza la búsqueda nativa en SoundCloud (scsearch1:)
        termino_busqueda = busqueda if es_url else f"scsearch1:{busqueda}"
        
        opts_busqueda = {
            'extract_flat': True,
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
        }

        with yt_dlp.YoutubeDL(opts_busqueda) as ytdl_search:
            info = await loop.run_in_executor(
                None, lambda: ytdl_search.extract_info(termino_busqueda, download=False)
            )
        
        if not info:
            return await mensaje_espera.edit(content="❌ No se encontró la canción en SoundCloud.")

        if 'entries' in info and info['entries']:
            datos_track = info['entries'][0]
        else:
            datos_track = info

        track_id = datos_track.get('id')
        url_track = datos_track.get('webpage_url') or datos_track.get('url')
        titulo = str(datos_track.get('title', 'Canción Desconocida'))
        uploader = str(datos_track.get('uploader', 'Artista Desconocido'))
        segundos = datos_track.get('duration', 0)
        duracion = str(timedelta(seconds=int(segundos))) if segundos else "Desconocida"
        thumbnail = str(datos_track.get('thumbnail', ''))

        # Descarga el audio desde SoundCloud
        opts_descarga = {
            'format': 'bestaudio/best',
            'outtmpl': f'/tmp/{track_id}.%(ext)s',
            'noplaylist': True,
            'nocheckcertificate': True,
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'keepvideo': False,
        }

        with yt_dlp.YoutubeDL(opts_descarga) as ytdl_dl:
            await loop.run_in_executor(
                None, lambda: ytdl_dl.extract_info(url_track, download=True)
            )

        filename_base = f"/tmp/{track_id}"
        filename = f"{filename_base}.mp3"
        
        if not os.path.exists(filename):
            for ext in ['m4a', 'ogg', 'opus', 'wav']:
                posible_archivo = f"{filename_base}.{ext}"
                if os.path.exists(posible_archivo):
                    filename = posible_archivo
                    break

        if not os.path.exists(filename):
            return await mensaje_espera.edit(content="❌ Error: No se pudo procesar la pista de SoundCloud.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return await mensaje_espera.edit(content=f"❌ Error al procesar la canción: {e}")

    # Reemplazar la pista si ya se reproducía algo
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    voice_client.is_music = True
    voice_client.archivo_musica = filename
    voice_client.segundos_acumulados = 0 
    voice_client.inicio_tiempo = time.time() 

    source = discord.FFmpegPCMAudio(filename, **FFMPEG_LOCAL_OPTIONS)
    voice_client.play(source)

    embed_music = discord.Embed(
        title="🟠 Reproduciendo desde SoundCloud",
        description=f"**[{titulo}]({url_track})**\n👤 *{uploader}*",
        color=discord.Color.orange()
    )
    embed_music.add_field(name="⏱️ Duración", value=f"`{duracion}`", inline=True)
    embed_music.add_field(name="🎧 Pedido por", value=ctx.author.mention, inline=True)
    if thumbnail:
        embed_music.set_thumbnail(url=thumbnail)

    await mensaje_espera.delete()
    await ctx.send(embed=embed_music)

@bot.command(name="resume")
async def resume(ctx):
    """Reanuda la canción pausada."""
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_paused():
        voice_client.inicio_tiempo = time.time()
        voice_client.resume()
        await ctx.send("▶️ Música reanudada.")
    else:
        await ctx.send("⚠️ La música no está pausada.")

@bot.command(name="stop", aliases=["leave"])
async def stop(ctx):
    """Detiene la música por completo y desconecta al bot."""
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client:
        archivo_a_borrar = getattr(voice_client, 'archivo_musica', None)
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
        await voice_client.disconnect()
        await ctx.send("🛑 Reproducción finalizada y bot desconectado.")

        if archivo_a_borrar and os.path.exists(archivo_a_borrar):
            try:
                os.remove(archivo_a_borrar)
            except Exception as e:
                print(f"No se puede borrar el archivo temporal: {e}")
    else:
        await ctx.send("⚠️ El bot no está conectado a ningún canal de voz.")

@bot.command(name="sorteo")
@commands.has_permissions(administrator=True)
async def lanzar_sorteo(ctx):
    """Lanza el anuncio del sorteo premium en el canal actual."""
    embed = discord.Embed(
        title="🔥 ¡Apertura del sorteo PREMIUM! 🔥",
        description=f"Se ha abierto un sorteo exclusivo en la comunidad de Qaybio.\n\n"
                    f"🏆 **Premio:** ¡Un gran premio especial de 2000 monedas en juego!\n"
                    f"🎟️ **Costo de inscripción:** `{Precio_sorteo}` monedas 🪙\n\n"
                    f"Presiona el botón de abajo para pagar tu entrada y registrar tus datos. "
                    f"El bot descontará automáticamente las monedas de tu banco.",
        color=discord.Color.red()
    )

    embed.set_footer(text="Asegúrate de tener el saldo suficiente antes de hacer clic.")

    await ctx.send(embed=embed, view=SorteoView())
    try:
        await ctx.message.delete()
    except:
        pass

# --- EJECUCIÓN SEGURA ---
# Se obtiene el token desde las variables de entorno de Render o local.
TOKEN = os.getenv("DISCORD_TOKEN", "MTUwOTM4MjI5NTkwNjQxODc4OA.GrcSZz.k4p7ILmd9ftUzG8EWIu-oyQ5BKMRZXDVymWk2U")

def iniciar_bot():
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Error al arrancar el bot de Discord: {e}")

if __name__ == "__main__":
    if TOKEN:
        print("🚀 Iniciando procesos en paralelo de Plátano-Bot...")
        
        # 1. Hilo secundario para Discord Bot
        t = threading.Thread(target=iniciar_bot)
        t.daemon = True
        t.start()
        
        # 2. Hilo principal para servidor Flask (Render detecta dinámicamente PORT)
        puerto = int(os.environ.get("PORT", 10000))
        try:
            app.run(host='0.0.0.0', port=puerto, debug=False, use_reloader=False)
        except KeyboardInterrupt:
            print("\n🛑 Servidor apagado localmente por el usuario.")
    else:
        print("❌ ERROR: No se ha detectado la variable de entorno DISCORD_TOKEN.")
