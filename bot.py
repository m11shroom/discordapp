import discord
from discord.ext import commands
from discord import app_commands
import os

# ============================
#  НАСТРОЙКИ
# ============================
TOKEN = "MTUxMzYwOTg5ODA5OTg2Nzc5OA.GfAgkW.Dhifn648GX2ISKqJYszTd89uAE-_euG4SeXdsk"   # <-- замени на свой токен

# ============================
#  ИНИЦИАЛИЗАЦИЯ
# ============================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# active_games: {message_id: GameState}
active_games = {}


# ============================
#  ИГРОВОЕ СОСТОЯНИЕ
# ============================
class GameState:
    def __init__(self, challenger: discord.User, opponent: discord.User, max_num: int):
        self.challenger = challenger   # угадывает
        self.opponent   = opponent     # загадывает
        self.max_num    = max_num
        self.secret     = None         # загаданное число (None пока не загадано)
        self.attempts   = []           # список попыток [(число, "high"/"low"/"win")]
        self.finished   = False

    def guess(self, number: int) -> str:
        if number < self.secret:
            result = "low"
        elif number > self.secret:
            result = "high"
        else:
            result = "win"
            self.finished = True
        self.attempts.append((number, result))
        return result

    def render_board(self) -> str:
        """Возвращает текстовое игровое поле."""
        lines = []
        for num, result in self.attempts:
            if result == "low":
                lines.append(f"📈  **{num}** — слишком мало")
            elif result == "high":
                lines.append(f"📉  **{num}** — слишком много")
            else:
                lines.append(f"✅  **{num}** — УГАДАЛ!")
        return "\n".join(lines) if lines else "*Попыток ещё не было*"


# ============================
#  ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ: EMBED
# ============================
def build_embed(game: GameState, status: str = "playing") -> discord.Embed:
    attempt_count = len(game.attempts)

    if status == "waiting":
        color = discord.Color.yellow()
        title = "🎮 Угадай число — ожидание"
        desc = (
            f"**{game.opponent.display_name}**, загадай число от **1** до **{game.max_num}**!\n"
            f"Нажми кнопку «Загадать» ниже."
        )
    elif status == "playing":
        color = discord.Color.blurple()
        title = f"🎮 Угадай число | Попытка #{attempt_count + 1}"
        desc = (
            f"**{game.challenger.display_name}** угадывает число от **1** до **{game.max_num}**\n"
            f"Загадал: **{game.opponent.display_name}**\n\n"
            f"**История попыток:**\n{game.render_board()}"
        )
    elif status == "win":
        color = discord.Color.green()
        title = "🎉 Победа!"
        secret = game.attempts[-1][0]
        desc = (
            f"**{game.challenger.display_name}** угадал число **{secret}** "
            f"за **{attempt_count}** попыток!\n\n"
            f"**История:**\n{game.render_board()}"
        )
    else:
        color = discord.Color.red()
        title = "🛑 Игра остановлена"
        desc = game.render_board()

    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_footer(text=f"Challenger: {game.challenger.display_name} vs Setter: {game.opponent.display_name}")
    return embed


# ============================
#  МОДАЛКА: ЗАГАДАТЬ ЧИСЛО
# ============================
class SetNumberModal(discord.ui.Modal, title="Загадай число"):
    def __init__(self, game: GameState, view: discord.ui.View, message: discord.Message):
        super().__init__()
        self.game    = game
        self.view    = view
        self.message = message
        self.number_input = discord.ui.TextInput(
            label=f"Введи число от 1 до {game.max_num}",
            placeholder=f"Например: 42",
            min_length=1,
            max_length=len(str(game.max_num)),
        )
        self.add_item(self.number_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.number_input.value.strip()
        if not raw.isdigit():
            await interaction.response.send_message("❌ Введи целое число!", ephemeral=True)
            return

        number = int(raw)
        if number < 1 or number > self.game.max_num:
            await interaction.response.send_message(
                f"❌ Число должно быть от 1 до {self.game.max_num}!", ephemeral=True
            )
            return

        self.game.secret = number

        # Обновляем сообщение на игровое поле
        new_view = GameView(self.game, self.message)
        embed = build_embed(self.game, status="playing")
        await self.message.edit(embed=embed, view=new_view)
        await interaction.response.send_message(
            f"✅ Число загадано! Теперь **{self.game.challenger.display_name}** будет угадывать.",
            ephemeral=True
        )


# ============================
#  МОДАЛКА: УГАДАТЬ ЧИСЛО
# ============================
class GuessModal(discord.ui.Modal, title="Угадай число"):
    def __init__(self, game: GameState, message: discord.Message):
        super().__init__()
        self.game    = game
        self.message = message
        self.number_input = discord.ui.TextInput(
            label=f"Твоя догадка (1 — {game.max_num})",
            placeholder="Например: 50",
            min_length=1,
            max_length=len(str(game.max_num)),
        )
        self.add_item(self.number_input)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.number_input.value.strip()
        if not raw.isdigit():
            await interaction.response.send_message("❌ Введи целое число!", ephemeral=True)
            return

        number = int(raw)
        if number < 1 or number > self.game.max_num:
            await interaction.response.send_message(
                f"❌ Число должно быть от 1 до {self.game.max_num}!", ephemeral=True
            )
            return

        result = self.game.guess(number)

        if result == "win":
            embed = build_embed(self.game, status="win")
            await self.message.edit(embed=embed, view=None)
            await interaction.response.send_message(
                f"🎉 **{self.game.challenger.display_name}** угадал за {len(self.game.attempts)} попыток!",
                ephemeral=False
            )
        else:
            embed = build_embed(self.game, status="playing")
            new_view = GameView(self.game, self.message)
            await self.message.edit(embed=embed, view=new_view)
            hint = "📈 Мало!" if result == "low" else "📉 Много!"
            await interaction.response.send_message(
                f"{hint} Попытка #{len(self.game.attempts)}",
                ephemeral=True
            )


# ============================
#  VIEW: КНОПКА «ЗАГАДАТЬ»
# ============================
class WaitingView(discord.ui.View):
    def __init__(self, game: GameState, message_ref):
        super().__init__(timeout=300)
        self.game        = game
        self.message_ref = message_ref  # будет заполнено после отправки

    @discord.ui.button(label="🤫 Загадать число", style=discord.ButtonStyle.success)
    async def set_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.opponent.id:
            await interaction.response.send_message(
                "❌ Только **загадывающий** нажимает эту кнопку!", ephemeral=True
            )
            return
        modal = SetNumberModal(self.game, self, self.message_ref)
        await interaction.response.send_modal(modal)


# ============================
#  VIEW: КНОПКИ ИГРЫ
# ============================
class GameView(discord.ui.View):
    def __init__(self, game: GameState, message: discord.Message):
        super().__init__(timeout=600)
        self.game    = game
        self.message = message

    @discord.ui.button(label="🎯 Угадать", style=discord.ButtonStyle.primary)
    async def guess_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.challenger.id:
            await interaction.response.send_message(
                "❌ Только **угадывающий** нажимает эту кнопку!", ephemeral=True
            )
            return
        modal = GuessModal(self.game, self.message)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🛑 Сдаться", style=discord.ButtonStyle.danger)
    async def surrender_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.game.challenger.id, self.game.opponent.id):
            await interaction.response.send_message("❌ Ты не участник этой игры.", ephemeral=True)
            return
        self.game.finished = True
        embed = build_embed(self.game, status="stopped")
        embed.description = (
            f"**{interaction.user.display_name}** сдался.\n"
            f"Загаданное число было: **{self.game.secret}**\n\n"
            + self.game.render_board()
        )
        await self.message.edit(embed=embed, view=None)
        await interaction.response.send_message("🛑 Игра завершена.", ephemeral=True)


# ============================
#  SLASH-КОМАНДА /угадай
# ============================
@bot.tree.command(name="угадай", description="Начать игру Угадай число с другим игроком")
@app_commands.describe(
    opponent="Игрок, который будет загадывать число",
    maximum="Максимальное число (по умолчанию 100)"
)
async def slash_guess(
    interaction: discord.Interaction,
    opponent: discord.User,
    maximum: int = 100
):
    if opponent.bot:
        await interaction.response.send_message("❌ Нельзя играть с ботом.", ephemeral=True)
        return
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("❌ Нельзя играть с самим собой.", ephemeral=True)
        return
    if maximum < 2:
        await interaction.response.send_message("❌ Максимум должен быть не меньше 2.", ephemeral=True)
        return

    game = GameState(
        challenger=interaction.user,
        opponent=opponent,
        max_num=maximum
    )

    embed = build_embed(game, status="waiting")

    # Отправляем сообщение — потом передадим его в View
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    view = WaitingView(game, message)
    view.message_ref = message
    await message.edit(view=view)


# ============================
#  СИНХРОНИЗАЦИЯ КОМАНД
# ============================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Бот запущен как {bot.user}")
    print(f"   Slash-команды синхронизированы!")
    print(f"   Ссылка для добавления: https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot+applications.commands&permissions=2048")


# ============================
#  ЗАПУСК
# ============================
bot.run(TOKEN)
