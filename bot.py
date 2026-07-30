import discord
from discord.ext import commands
import re
import time
from datetime import timedelta
import threading
from flask import Flask
import edge_tts
import os  # Necesario para leer el Token de forma segura
from PIL import Image, ImageDraw, ImageOps, ImageFont
import io
import requests
import asyncio
import yt_dlp
import sqlite3
import random
from discord.ext import tasks

# --- CONFIGURACIÓN DE FLASK PARA HUGGING FACE ---
app = Flask('')

@app.route('/')
def home():
    return "Bot está vivo!"

@app.route('/status')
def status():
    return "OK"

# --- CONFIGURACIÓN DEL BOT ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Habilitado para detectar nuevos miembros
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 🔒 SEGURIDAD
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
        "logo" : "🛡️"
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
        "descripcion": "Acceso a canales exclusivos, canales de voz premium y un color especial en el chat"
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
        "descpcion": "...."
    },
    "Acceso_a_clanes": {
        "nombre": "Clanes",
        "precio": 1000,
        "rol_id": 44444444444444444444,
        "descripcion": "...."
    },
    "sorteo": {
        "nombre": "Inscripción sorteo PRemium 🎟️",
        "precio": 2000,
        "rol_id": 0,
        "descripcion": "Participación activa de un soreo gigante"
    }
}

salas_dinamicas = []

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],

    'outtmpl': 'music_cache_%(guild_id)s.%(ext)s',
}

FFMPEG_LOCAL_OPTIONS = {
    'options': '-vn',
}

FFMPEG_STREAM_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)

def inizializar_db():
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

inizializar_db()

MENSAJES_PROMO = [
    "🔥 ¡Promociones nuevas en nuestra página! No te las pierdas.",
    "🎁 Únete a la página hoy y reclama tus puntos en el servidor.",
    "🛒 ¡Aprovecha! Compra productos exclusivos por mil puntos.",
    "🚀 Qaybio se actualiza constantemente, visítanos para ver las novedades."
]

ID_CANAL_PROMOCIONES = 1522356604186661025

ID_CANAL_ANUNCIO_COMPRAS = 1529240157188784128

ID_CANAL_INVITACIONES = 1508947735561371720

Precio_sorteo = 2000
ID_canal_LOGS_sorteo = 1529242250775892018

async def cargar_invitaciones():
    """Cargar todas las invitaciones del caché"""
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invitaciones_cache[guild.id] = {invite.code: invite.uses for invite in invites}
        except discord.Forbidden:
            print(f"⚠️ No tengo permisos suficientes para leer invitaciones: {guild.name}")
        except Exception as e:
            print(f"❌ Error al cargar las invitacions {e}")

@tasks.loop(hours=3)
async def promocion_diaria():
    canal = bot.get_channel(ID_CANAL_PROMOCIONES)
    if canal:
        mensaje_elegido = random.choice(MENSAJES_PROMO)

        embed = discord.Embed(
            title = "🌐 ¡Visita Qaybio!",
            description=f"{mensaje_elegido}\n\n"
                        f"👉 Entra aquí para ganar **50 monedas**: [Ir a Qaybio](https://tiendavirtual-801x.onrender.com/)"
                        f"Escribe el comando `!link` y te enviaré tu enlace único por mensaje privado.",
            color= discord.Color.gold()
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

    if resultado is None or resultado[0] !=mes_actual_str:
        print(f"📆 [SISTEMA MENSUAL] ¡Ha comenzado un nuevo periodo ({mes_actual_str}) ! Repartiendo 50 monedas...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios(
                used_id TEXT PRIMARY KEY,
                monedas INTEGER DEFAULT 0           
            )
        """)

        cursor.execute("UPDATE usuarios SET monedas = monedas + 50")

        if resultado is None:
            cursor.execute("INSERT INTO control_premios (clave, valor) VALUES ('ultimo_mes_premiado', ?)", (mes_actual_str,))
        else:
            cursor.execute("UPDATE control_premios SET valor = ? WHERE clave = 'ultimo_mes_premiado'", (mes_actual_str,))

        conn.commit()
        print("💰 [DISTEMA MENSUAL] Se han abonado 50 monedas a todos los usuarios de la base de datos")

        canal = bot.get_channel("TU_ID_DEL CANAL")
        if canal:
            embed = discord.Embed(
                title="🎁 ¡Legó tu recompensa mensual!",
                description=f"Se han depositado **50 monedas** 🪙 automaticamente en las cuentas de todos los usuarios\n\n"
                            f"Revisa tu saldo con `!dinero`",
                color=discord.Color.green()
            )
            await canal.send(embed=embed)
        
    conn.close()

@bot.event
async def on_ready():
    bot.add_view(TicketCOnsultaView())
    bot.add_view(SalaVozView())
    bot.add_view(SorteoView())

    await  cargar_invitaciones()

    print(f"✅ Bot conectado como {bot.user}")
    
    if not promocion_diaria.is_running():
        promocion_diaria.start()
    if not recompensa_mensual_autonoma.is_running():
        recompensa_mensual_autonoma.start()

class RegistroSorteoModal(discord.ui.Modal, title= "Inscripcion del Sorteo Premium"):
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
        max_length= 200
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id= str(interaction.user.id)

        conn = sqlite3.connect("economia_qaybio.db")
        cursor= conn.cursor()

        cursor.execute("SELECT monedas FROM usuarios WHERE user_id=?", (user_id))
        resultado= cursor.fetchone()
        monedas_actuales = resultado[0] if resultado else 0

        if  monedas_actuales < Precio_sorteo:
            conn.close()
            return await interaction.response.send_message(
                f"❌ Inscripción cancelada. Ya no cuentas con las **{Precio_sorteo}** monedas necesarias (Tienes: {monedas_actuales} 🪙).",
                ephemeral= True
            )
        
        try:
            cursor.execute("UPDATE usuarios SET monedas = monedas - ? WHERE user_id = ?", (Precio_sorteo, user_id))
            conn.commit()
        except Exception as e:
            conn.close()
            print(f"Error en la base de datos al comprar sorteo: {e}")
            return await interaction.response.send_message("❌Ocurrió un error al intentar procesar el pago. Intentalo de nuevo", ephemeral= True)
        
        conn.close()

        canal_privado = interaction.guild.get_channel(ID_canal_LOGS_sorteo)
        if canal_privado:
            embed_log = discord.Embed(
                title="🎟️ Nueva incripción recibida",
                description= f"El usuario {interaction.user.mention} se ha inscrito exitosamente al cobrarle las monedas.",
                color= discord.Color.gold()
            )

            embed_log.add_field(name="👤 Usuario Discord", value= f"{interaction.user} (ID: `{interaction.user.id}`)", inline=True)
            embed_log.add_field(name="📛 Nombre Registrado", value=self.nombre_real.value, inline=True)
            embed_log.add_field(name="💬 Mensaje/Comentario", value=self.comentarios.value or "*Ninguno*", inline=False)
            embed_log.add_field(name="💰 Transacción", value=f"Se descontaron **{Precio_sorteo}** monedas de tu saldo.", inline=False)
            embed_log.set_thumbnail(url= interaction.user.display_avatar.url)

            await canal_privado.send(embed=embed_log)

        canal_anuncios = interaction.guild.get_channel(ID_CANAL_ANUNCIO_COMPRAS)
        if canal_anuncios:
            embed_anuncio_publico = discord.Embed(
                title="🎟️ ¡Nuevo APrticipante en sorteo PREMIUM! 🎟️",
                description=f"{interaction.user.mention} ha gastado **{Precio_sorteo}** monedas",
                color= discord.Color.red()
            )

            embed_anuncio_publico.set_thumbnail(url=interaction.user.display_avatar.url)
            embed_anuncio_publico.set_footer(text="¡Aún cupos disponibles!, has tu compra antes de que se termine")

            await canal_anuncios.send(embed=embed_anuncio_publico)

        embed_usuario = discord.Embed(
            title="✅ ¡Inscripción completada!",
            description=f"Has pagado **{Precio_sorteo}** monedas 🪙 y tus datos se registraron correctamente. \n"
                        f"¡Mucha suerte en el sorteo!",
            color=discord.Color.green()
        )

        embed_usuario.add_field(name="📛 Registrado como:", value=self.nombre_real.value, inline=True)
        embed_usuario.add_field(name="💳 NUevo saldo", value=f"{monedas_actuales-Precio_sorteo} 🪙", inline=True)

        await interaction.response.send_message(embed=embed_usuario, ephemeral=True)

class SorteoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Inscribirse al sorteo (2,000 🪙)", style= discord.ButtonStyle.danger, emoji="🎟️", custom_id="btn_inscripcion_sorteo")
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
    def __init__(self):  # CORREGIDO: Llevaba doble guion bajo 'init_'
        super().__init__(timeout=None)  # CORREGIDO: Llevaba doble guion bajo 'init_'

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
                description=datos["descripcion"][:50],  # Recorte seguro para evitar bugs de límite
                emoji=datos["logo"]
            ))
        super().__init__(placeholder="Elige el clan al que deseas unirte...", min_values=1, max_values=1, options=opciones)

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        clan_elegido = CLANES[self.values[0]]
        rol = guild.get_role(clan_elegido["rol_id"])

        if not rol:
            return await interaction.response.send_message("❌ Error: El rol de este clan no está configurado correctamente en el bot.", ephemeral=True)

        # Verificar si ya posee algún rol de los clanes existentes para evitar duplicados
        for clan in CLANES.values():
            if guild.get_role(clan["rol_id"]) in interaction.user.roles:
                return await interaction.response.send_message("⚠️ Ya perteneces a un clan actualmente. Debes salir de tu clan actual primero.", ephemeral=True)

        try:
            await interaction.user.add_roles(rol)
            await interaction.response.send_message(f"🎉 ¡Felicidades! Te has unido exitosamente al clan **{clan_elegido['nombre']}**.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ El bot no tiene permisos jerárquicos suficientes para darte este rol.", ephemeral=True)

# Formulario Emergente (Modal) para Solicitar un nuevo Clan
class CrearClanModal(discord.ui.Modal, title="Formulario de Creación de Clan"):
    nombre_clan = discord.ui.TextInput(label="Nombre del Clan", placeholder="Ej: Los Imparables", min_length=3, max_length=30)
    desc_clan = discord.ui.TextInput(label="Descripción Breve", style=discord.TextStyle.long, placeholder="Explica de qué trata tu clan y tus objetivos...", min_length=10, max_length=200)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        # Configurar los permisos iniciales del canal de tickets (Administradores y el solicitante)
        permisos = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False), # Oculto al público
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True) # El bot
        }

        # Intentamos buscar canales con formato secuencial para nombrar el ticket
        numero_ticket = 1
        for channel in guild.channels:
            if channel.name.startswith("ticket-clan-"):
                try:
                    num = int(channel.name.split("-")[-1])
                    if num >= numero_ticket:
                        numero_ticket = num + 1
                except ValueError:
                    pass

        # Crear el canal de texto privado dentro del servidor
        canal_ticket = await guild.create_text_channel(
            name=f"ticket-clan-{numero_ticket}",
            overwrites=permisos,
            topic=f"Solicitud de clan de {interaction.user.name}"
        )

        # Mensaje estético dentro del ticket creado
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

# Vista Principal del comando !clan con los 4 botones requeridos
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
            # Contamos cuántos miembros en el servidor tienen asignado el rol de este clan
            num_miembros = len(rol.members) if rol else 0
            
            info_clan = f"**Logo:** {datos['logo']}\n**Miembros actuales:** `{num_miembros}`\n**Descripción:** {datos['descripcion']}"
            embed.add_field(name=f"🔹 {datos['nombre']}", value=info_clan, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Unirse a un Clan", style=discord.ButtonStyle.success, emoji="⚔️")
    async def unirse_clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Desplegamos el menú dinámico para que escoja cuál quiere
        vista_menu = discord.ui.View()
        vista_menu.add_item(SeleccionarClanMenu())
        await interaction.response.send_message("Selecciona el clan al que deseas ingresar:", view=vista_menu, ephemeral=True)

    @discord.ui.button(label="Crear Clan", style=discord.ButtonStyle.secondary, emoji="👑")
    async def crear_clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Desplegamos el formulario nativo flotante
        await interaction.response.send_modal(CrearClanModal())

    @discord.ui.button(label="Salir del Clan", style=discord.ButtonStyle.danger, emoji="🚪")
    async def salir_clan(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        clanes_removidos = []

        # Buscamos si tiene algún rol de clan y lo removemos
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

class consultaModal(discord.ui.Modal, title ="Formulario de Consulta"):
    asunto_consulta = discord.ui.TextInput(
        label = "Asunto / tema corto",
        placeholder="Ej: Mejoras clan / Duda de evento",
        min_length= 5,
        max_length= 50
    )
    detalle_consulta = discord.ui.TextInput(
        label = "Escribe tu consulta detallada aquí",
        style = discord.TextStyle.long,
        placeholder= "Escribe a detalle tu consulta para que el staff pueda ayudarte...",
        min_length= 15,
        max_length= 500
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild

        permisos = {
            guild.default_role: discord.PermissionOverwrite(read_messages= False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        numero_ticket = 1
        for channel in guild.channels:
            if channel.name.startswith("ticket-consulta-"):
                try:
                    num= int(channel.name.split("-")[-1])
                    if num >= numero_ticket:
                        numero_ticket = num + 1
                except ValueError:
                    pass


        canal_ticket = await guild.create_text_channel(
            name = f"ticket-consulta-{numero_ticket}",
            overwrites=permisos,
            topic= f"Consulta privada de {interaction.user.name}"
        )

        embed_soporte = discord.Embed(
            title= f"Consulta de Soporte #{numero_ticket}",
            description=f"Hola {interaction.user.mention}, un miembro del staff atenderá tu consulta lo antes posible",
            color=discord.Color.green()
        )
        embed_soporte.add_field(name="Asunto", value=self.asunto_consulta.value, inline=False)
        embed_soporte.add_field(name="Detalle de la consulta", value=self.detalle_consulta.value, inline=False)
        embed_soporte.set_footer(text="Platano-Bot | Sistema de soporte", icon_url=guild.me.display_avatar.url)

        await canal_ticket.send(embed=embed_soporte)
        await interaction.response.send_message(f"¡Tu consulta fue creada! Ve a tu canal privado aquí {canal_ticket.mention}", ephemeral=True)

class TicketCOnsultaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Realizar consulta", style=discord.ButtonStyle.success, emoji="💬", custom_id="btn_realizar_consulta")
    async def realizar_consulta(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(consultaModal())

class SalaVozView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Crear Sala de Voz", style=discord.ButtonStyle.primary, emoji="🔊", custom_id="btn_crear_sala_voz")
    async def crear_sala(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild

        nombre_canal = f"🔊 Sala de {interaction.user.display_name}"

        try:
            nuevo_canal = await guild.create_voice_channel(name=nombre_canal)
            salas_dinamicas.append(nuevo_canal.id)

            await interaction.response.send_message(f"✅ Tu sala de voz temporal ha sido creada: {nuevo_canal.mention}\n*Se eliminará automáticamente cuando quede vacía.*", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ El bot no tiene permisos para crear canales de voz.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ocurrió un error: {e}", ephemeral=True)

# --- EVENTO DE AUTO-ROL ---
@bot.event
async def on_member_join(member):
    # 📌 REEMPLAZA ESTE NÚMERO POR EL ID REAL DE TU ROL:
    # Ve a Discord -> Ajustes de Servidor -> Roles -> Clic derecho al rol -> Copiar ID
    ID_DEL_CANAL = 1508947735561371720
    ID_DEL_ROL = 1503573657950097479

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
    except Exception as e :
        print("❌ error al procesar invitaciones: {e}")
    
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
                title="📈 ¡Nueva invitación exitosa! ",
                description= f"¡El enlace de invitación de {invitador.mention} ha sido utilizado!",
                color=discord.Color.green()
            )
            embed_invite.add_field(name="👤 invitado", value=member.mention, inline=True)
            embed_invite.add_field(name="👤 invitado por", value=invitador.mention, inline=True)
            embed_invite.add_field(name="🎟️ Código usado", value=f"+10 monedas 🪙 (Total actual: {nuevas_monedas})", inline=False)
            embed_invite.set_thumbnail(url=member.display_avatar.url)
            embed_invite.set_footer(text="¡Gracias por ayudar a que crezca la comunidaad!")

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
            archivo_banner = "banner.jpeg"
            for extension in ["banner.png", "banner.jpg", "banner.jpeg"]:
                if os.path.exists(extension):
                    archivo_banner = extension
                    break

            if archivo_banner:
                background = Image.open(archivo_banner).convert("RGBA")
            else:
                background = Image.new("RGBA", (800, 400), color= (44, 47, 51, 255))
        
            avatar_url = member.display_avatar.url
            response = requests.get(avatar_url)
            avatar_img = Image.open(io.BytesIO(response.content)).convert("RGBA")

            avatar_size = (100, 100)
            avatar_img = avatar_img.resize(avatar_size, Image.Resampling.LANCZOS)

            mascara = Image.new("L", avatar_size, 0)
            draw_mask = ImageDraw.Draw(mascara)
            draw_mask.ellipse((0,0) + avatar_size, fill= 255)

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

            draw.ellipse([x0, y0, x1, y1], outline= color_borde, width=grosor_borde)

            texto_bienvenida = f"¡Bienvenido, {member.name}!"
            texto_miembro = f"Miembro #{len(guild.members)}"

            try:
                fuente_principal = ImageFont.truetype("BILLO___.TTF", 26)
                fuente_secundaria = ImageFont.truetype("BILLO___.TTF", 28)
            except IOError:
                print("⚠️ No se encontró BILLO___.TTF, usando fuente por defecto.")
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

            await canal_bienvenida.send(content= mensaje_personalizado, file= archivo_discord)
            print(f"Banner de bienvenida enviado para  {member.name}")

        except Exception as e:
            print(f"Error al generar el banner de bienvenida: {e}")

@bot.event
async def on_invite_create(invite):
    """Actualiza el caché cuando alguien crea una nueva invitación"""
    if invite.guild.id not in invitaciones_cache:
        invitaciones_cache[invite.guild.id] = {}
    invitaciones_cache[invite.guild.id][invite.code] = invite.uses

@bot.event
async def on_invite_delete(invite):
    """Limpia el código del caché cuando se crean nuevas invitaciones."""
    if invite.guild.id in invitaciones_cache:
        invitaciones_cache[invite.guild.id].pop(invite.code, None)

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is not None:
        canal_previo = before.channel

        if canal_previo.id in salas_dinamicas and len(canal_previo.members) == 0:
            try:
                await canal_previo.delete(reason="Sala dinámica vacía.")
                salas_dinamicas.remove(canal_previo.id)
                print(f"🗑️ Sala de voz temporal '{canal_previo.name}' eliminada por quedarse vacía.")
            except discord.Forbidden:
                print(f"❌ Sin permisos para eliminar la sala de voz vacía: {canal_previo.name}")
            except Exception as e:
                print(f"❌ Error al intentar borrar sala dinámica: {e}")

@bot.event
async def on_message(message):
    # 🚫 IGNORAR MENSAJES DEL PROPIO BOT
    if message.author == bot.user:
        return
        
    # 🛡️ FILTROS DE SEGURIDAD (Mensajes prohibidos)
    contenido = message.content.lower() if message.content else ""
    for palabra in palabras_prohibidas:
        if palabra in contenido:
            try:
                await message.delete()
            except:
                pass
            return await message.channel.send(f"{message.author.mention} 🚫 Mensaje prohibido.", delete_after=5)
        
    # ⏳ CONTROL ANTISPAM
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

    # 🎮 PROCESAR COMANDOS NORMALES (!dinero, !play, etc.)
    await bot.process_commands(message)

@bot.listen('on_message')
async def detector_webhook_monedas(message):
    # 🕵️‍♂️ Buscamos la palabra clave sin importar si viene de un webhook, bot o usuario
    contenido_texto = message.content if message.content else ""
    
    # Si viene empaquetado en un Embed, extraemos el texto de la descripción
    if not contenido_texto and message.embeds:
        for embed in message.embeds:
            if embed.description and "SISTEMA_MONEDAS_RECOMPENSA:" in embed.description:
                contenido_texto = embed.description
                break

    if "SISTEMA_MONEDAS_RECOMPENSA:" in contenido_texto:
        try:
            # Forzamos la extracción quitando cualquier espacio o salto de línea
            user_id = contenido_texto.split("SISTEMA_MONEDAS_RECOMPENSA:")[1].strip()
            print(f"\n📥 [¡LISTENER CAPTURADO!] Se detectó clic para el ID: {user_id}")
            
            # Conexión directa a la base de datos local
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
                print(f"💰 [ÉXITO EN CONSOLA] +50 monedas añadidas a {user_id}")
            else:
                cursor.execute("INSERT INTO usuarios (user_id, monedas) VALUES (?, 50)", (user_id,))
                print(f"🆕 [ÉXITO EN CONSOLA] Nuevo usuario registrado con 50 monedas: {user_id}")
                
            conn.commit()
            conn.close()
            
            # Intentar enviar confirmación visual a Discord
            try:
                usuario_discord = await bot.fetch_user(int(user_id))
                await message.channel.send(f"🪙 ¡Visita confirmada! {usuario_discord.mention} ha recibido **50 monedas** por apoyar a Qaybio.")
            except Exception as e:
                print(f"No se pudo enviar la confirmación en el chat: {e}")
                
            # Intentar borrar el mensaje plano del webhook
            try:
                await message.delete()
            except:
                pass

        except Exception as e:
            print(f"❌ Error interno en el Listener de monedas: {e}")

@bot.command(name="tienda", aliases=["store", "shop"])
async def mostrar_tienda(ctx):
    """Muestra los rangos disponibles para comprar con monedas de Qaybio."""
    embed = discord.Embed(
        title="🛒 tienda oficial de Rangos",
        description= "¡Utiliza tus monedas acumuladas para comprar rangos exclusivosen el servidor!\n\n"
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
        embed.add_field(name=f" 🔹 {nombre}", value=info_producto, inline=False)

    embed.set_footer(text="Platano bot • Economía e Interracciones", icon_url=ctx.guild.me.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(nombre="comprar", aliases=["buy", "camjear"])
async def comprar_rango(ctx, rango: str= None):
    """Procesa la compra de un rango descontando las monedas de la base de datos."""
    if not rango:
        return await ctx.send(f"⚠️ {ctx.author.mention}, debes especificar que rango que rango deseas comprar. Usa `!tienda` para ver las opciones.")
    
    rango = rango.lower()

    if rango not in TIENDA_ROLES:
        return await ctx.send(f"❌ {ctx.author.mention}, el rango `{rango}` no existe en la tienda. Revisa la lista usando `!tienda`.")
    
    producto = TIENDA_ROLES[rango]
    guild = ctx.guild
    rol_recompensa = guild.get_role(producto["rol_id"])

    if not rol_recompensa:
        return await ctx.send(f"❌ Error de configuración: El rol solicitado no existe o su ID está mal configurado en el código.")
    
    if rol_recompensa in ctx.author.roles:
        return await ctx.send(f"⚠️ {ctx.author.mention}, ¡tú ya posees el rango **{producto['nombre']}**!")
    
    user_id = str(ctx.author.id)

    conn = sqlite3.connect("economia_qaybio.db")
    cursor = conn.cursor()

    cursor.execute("SELECT monedas FROM usuarios WHERE user_id = ?", (user_id))
    resultado = cursor.fetchone()

    monedas_actuales = resultado[0] if resultado  else 0

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
                description=f"¡Atención comunidad! {ctx.author.mention} acaba de canjear sus monedas por un beneficio exclusivo",
                color=discord.Color.gold()
            )

            embed_anuncio.add_field(name="👤 Comprador", value=ctx.author.mention, inline=True)
            embed_anuncio.add_field(name="✨ Artículo adquirido", value=f"**{producto['nombre']}**", inline=True)
            embed_anuncio.set_thumbnail(url=ctx.author.display_avatar.url)
            embed_anuncio.set_footer(text="¡Sigue sumando monedas visitando nuestra página web! 🪙")

            await canal_anuncios.send(embed=embed_anuncio)

    except discord.Forbidden:
        conn = sqlite3.connect("economia_qaybio.db")
        cursor= conn.cursor()
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
    url_monedas = f"{"https://tiendavirtual-801x.onrender.com/"}/click?user_id={user_id}"
    
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
    """Envía el panel con el botón interactivo para crear salas de voz automáticas."""
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
    
    ticket = 1503799170409168966
    if ctx.channel.id != ticket:
        await ctx.send("❌ Usa esto en #tiket-consultas")
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
    # Eliminamos la lista de canales permitidos y la verificación if ctx.channel.id
    # Ahora se puede ejecutar donde sea que un Admin lo necesite.

    embed = discord.Embed(
        title="⚙️ Centro de Consultas y Soporte Técnico",
        description="¿Tienes alguna duda, reporte o inconveniente con el servidor?\n\nPresiona el botón de **💬 Realizar consulta** aquí abajo para abrir un canal privado y comunicarte directamente con la administración.",
        color=discord.Color.teal()
    )
    embed.set_footer(text="Plátano-Bot • Soporte del Servidor")
    
    # Imprime el panel con el botón interactivo en el canal actual
    await ctx.send(embed=embed, view=TicketCOnsultaView())
    
    try:
        await ctx.message.delete()
    except:
        pass

@bot.command()
async def clan(ctx):
    # Puedes restringir este comando a un canal específico si lo deseas cambiando o replicando la lógica del !ticket
    embed = discord.Embed(
        title="🛡️ Sistema de Gestión de Clanes",
        description="Gestiona tu lealtad, visualiza los clanes activos o solicita fundar uno nuevo usando las opciones interactivas de abajo.",
        color=discord.Color.dark_purple()
    )
    embed.set_footer(text="Plátano-Bot • Sistema de Facciones")
    
    # Desplegar el menú embebido junto con los 4 botones de ClanView
    await ctx.send(embed=embed, view=ClanView())

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    contenido = message.content.lower()

    # 🚫 Filtros de Seguridad
 
    for palabra in palabras_prohibidas:
        if palabra in contenido:
            await message.delete()
            return await message.channel.send(f"{message.author.mention} 🚫 Mensaje prohibido.", delete_after=5)

    # 🚫 Control de Spam
    ahora = time.time()
    user_id = message.author.id
    if user_id not in usuarios_mensajes:
        usuarios_mensajes[user_id] = []
    
    usuarios_mensajes[user_id].append(ahora)
    usuarios_mensajes[user_id] = [t for t in usuarios_mensajes[user_id] if ahora - t < 5]

    if len(usuarios_mensajes[user_id]) > 5:
        try:
            await message.author.timeout(timedelta(minutes=10), reason="Spam detectado")
            await message.channel.send(f"🚫 {message.author.mention} ha sido silenciado 10 min por spam.")
        except:
            pass
        return

    await bot.process_commands(message)

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
                    'options' : f'-vn -ss {int(voice_client.segundos_acumulados)}'
                }

                source_musica = discord.FFmpegPCMAudio(archivo_original_musica, **opciones_reanudar)

                voice_client.inicio_tiempo = time.time()
                bot.loop.call_soon_threadsafe(voice_client.play, source_musica)

        voice_client.play(source_tts, after=after_playing)
        
    except Exception as e:
        await ctx.send(f"❌ Error al reproducir el TTS: {e}")

@bot.command(name="play", aliases=["p"])
async def play(ctx, *, busqueda: str):
    """Busca y reproduce canciones configurando outtmpl como un diccionario válido para yt_dlp."""
    if not ctx.author.voice:
        return await ctx.send(f"⚠️ {ctx.author.mention}, ¡debes entrar a un canal de voz primero!")

    canal_voz = ctx.author.voice.channel
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not voice_client:
        voice_client = await canal_voz.connect()
    elif voice_client.channel != canal_voz:
        await voice_client.move_to(canal_voz)

    mensaje_espera = await ctx.send(f"🔍 Buscando **{busqueda}** en YouTube...")

    loop = bot.loop or asyncio.get_event_loop()
    try:
        filename_base = f"music_cache_{ctx.guild.id}"
        ytdl.params['outtmpl'] = {'default': f'{filename_base}.%(ext)s'}
        
        es_url = busqueda.startswith("http://") or busqueda.startswith("https://")
        termino_busqueda = busqueda if es_url else f"ytsearch1:{busqueda}"
        
        # Extraer metadatos de forma segura (download=False)
        info = await loop.run_in_executor(None, lambda: ytdl.extract_info(termino_busqueda, download=False))
        
        if not info:
            return await mensaje_espera.edit(content="❌ No se encontró el video.")

        if 'entries' in info:
            if len(info['entries']) == 0:
                return await mensaje_espera.edit(content="❌ Sin resultados.")
            datos_video = info['entries'][0]
        else:
            datos_video = info

        # Guardar metadatos en variables nativas limpias
        url_video = str(datos_video.get('webpage_url', ''))
        titulo = str(datos_video.get('title', 'Canción Desconocida'))
        segundos = datos_video.get('duration', 0)
        duracion = str(timedelta(seconds=int(segundos))) if segundos else "Desconocida"
        thumbnail = str(datos_video.get('thumbnail', ''))

        # Ejecutar la descarga real pasando el link directo
        try:
            await loop.run_in_executor(None, lambda: ytdl.extract_info(url_video, download=True))
        except Exception as download_error:
            print(f"[Descarga] Nota u observación durante la conversión: {download_error}")

        filename = f"{filename_base}.mp3"
        if not os.path.exists(filename):
            for ext in ['m4a', 'webm', 'opus', 'mp4']:
                if os.path.exists(f"{filename_base}.{ext}"):
                    filename = f"{filename_base}.{ext}"
                    break

        if not os.path.exists(filename):
            return await mensaje_espera.edit(content="❌ Error: No se pudo generar el archivo de audio local.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return await mensaje_espera.edit(content=f"❌ Error al procesar la canción: {e}")

    # Control de reproducción de audio de Discord
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()

    # Sincronización de tiempos para que no interfiera con tu comando !say
    voice_client.is_music = True
    voice_client.archivo_musica = filename
    voice_client.segundos_acumulados = 0 
    voice_client.inicio_tiempo = time.time() 

    source = discord.FFmpegPCMAudio(filename, **FFMPEG_LOCAL_OPTIONS)
    voice_client.play(source)

    # Enviar Embed con la información limpia
    embed_music = discord.Embed(
        title="🎵 Reproduciendo Ahora",
        description=f"**[{titulo}]({url_video})**" if url_video else f"**{titulo}**",
        color=discord.Color.red()
    )
    embed_music.add_field(name="⏱️ Duración", value=f"`{duracion}`", inline=True)
    embed_music.add_field(name="👤 Solicitado por", value=ctx.author.mention, inline=True)
    if thumbnail:
        embed_music.set_thumbnail(url=thumbnail)

    await mensaje_espera.delete()
    await ctx.send(embed=embed_music)

@bot.command(name="pause")
async def pause(ctx):
    """Pausa la canción actual."""
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_playing():
        tiempo_reproducido = time.time() - voice_client.inicio_tiempo
        voice_client.segundos_acumulados += tiempo_reproducido
        voice_client.pause()
        await ctx.send("⏸️ Música pausada.")
    else:
        await ctx.send("⚠️ No hay música reproduciéndose actualmente.")

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
        title= "🔥 ¡Apertura del sorteo PREMIUM! 🔥",
        description=f"Se ha abierto un sorteo exclusivo en la comunidad de Qaybio.\n\n"
                    f"🏆 **Premio:** ¡Un gran premio especial de 2000 monedas en juego!\n"
                    f"🎟️ **Costo de inscripción:** `{Precio_sorteo}` monedas 🪙\n\n"
                    f"Presiona el botón de abajo para pagar tu entrada y registrar tus datos. "
                    f"El bot descontará automáticamente las monedas de tu banco.",
        color=discord.Color.red()
    )

    embed.set_footer(text="Asegurate de tener el saldo suficiente antes de hacer clic.")

    await ctx.send(embed=embed, view=SorteoView())
    try:
        await ctx.message.delete()
    except:
        pass

# --- EJECUCIÓN SEGURA ---
token_seguro = "MTQ5Mjk2MTM5NjE1NjI3MjkwMQ.Ggbwkq.a1zcEPoB8xTw1fqa70tO_7K8Xw99xspz8erGOg"

def iniciar_bot():
    try:
        bot.run(token_seguro)
    except Exception as e:
        print(f"❌ Error al arrancar el bot de Discord: {e}")

if __name__ == "__main__":
    if token_seguro and token_seguro != "TU_TOKEN_AQUI":
        print("🚀 Iniciando procesos en paralelo de Plátano-Bot...")
        
        # 1. Ejecutamos el bot de Discord en un hilo secundario
        t = threading.Thread(target=iniciar_bot)
        t.daemon = True
        t.start()
        
        # 2. Corremos Flask en el hilo principal con el puerto corregido (7860) para congelar la consola
        try:
            app.run(host='0.0.0.0', port=7860, debug=False, use_reloader=False)
        except KeyboardInterrupt:
            print("\n🛑 Servidor apagado localmente por el usuario.")
    else:
        print("❌ ERROR: No has configurado tu variable 'token_seguro' con un token válido.")

