import discord
from discord.ext import commands
from discord import app_commands
import os

TOKEN = os.environ["TOKEN"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# active_games: {message_id: {"p1": user, "p2": user, "p1_choice": str, "p2_choice": str}}
active_games = {}

CHOICES = {
    "rock":     "✊ Камень",
    "scissors": "✌️ Ножницы",
    "paper":    "🖐 Бумага",
}

BEATS = {
    "rock":     "scissors",
    "scissors": "paper",
    "paper":    "rock",
}

EMOJI = {
    "rock": "✊",
    "scissors": "✌️",
    "paper": "🖐",
}


def get_result(p1_choice, p2_choice):
    if p1_choice == p2_choice:
        return "draw"
    if BEATS[p1_choice] == p2_choice:
        return "p1"
    return "p2"


def build_waiting_embed(p1: discord.User, p2: discord.User, p1_done: bool, p2_done: bool):
    desc = (
        f"{('✅' if p1_done else '⏳')} **{p1.display_name}** — {'выбрал' if p1_done else 'думает...'}\n"
        f"{('✅' if p2_done else '⏳')} **{p2.display_name}** — {'выбрал' if p2_done else 'думает...'}"
    )
    embed = discord.Embed(
        title="✊ Камень-ножницы-бумага",
        description=desc,
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="Нажми кнопку чтобы сделать ход — соперник не увидит твой выбор до конца")
    return embed


def build_result_embed(p1: discord.User, p2: discord.User, p1_choice: str, p2_choice: str):
    result = get_result(p1_choice, p2_choice)

    p1_line = f"**{p1.display_name}**: {EMOJI[p1_choice]} {p1_choice.capitalize()}"
    p2_line = f"**{p2.display_name}**: {EMOJI[p2_choice]} {p2_choice.capitalize()}"

    if result == "draw":
        title = "🤝 Ничья!"
        color = discord.Color.light_grey()
        winner_line = "Оба выбрали одно и то же!"
    elif result == "p1":
        title = f"🏆 Победил {p1.display_name}!"
        color = discord.Color.green()
        winner_line = f"{EMOJI[p1_choice]} бьёт {EMOJI[p2_choice]}"
    else:
        title = f"🏆 Победил {p2.display_name}!"
        color = discord.Color.green()
        winner_line = f"{EMOJI[p2_choice]} бьёт {EMOJI[p1_choice]}"

    embed = discord.Embed(
        title=title,
        description=f"{p1_line}\n{p2_line}\n\n{winner_line}",
        color=color,
    )
    embed.set_footer(text="Нажми «Сыграть снова» для новой игры")
    return embed


class ChoiceView(discord.ui.View):
    def __init__(self, game_id: int):
        super().__init__(timeout=300)
        self.game_id = game_id

    async def handle_choice(self, interaction: discord.Interaction, choice: str):
        game = active_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Игра не найдена.", ephemeral=True)
            return

        p1, p2 = game["p1"], game["p2"]
        if interaction.user.id not in (p1.id, p2.id):
            await interaction.response.send_message("❌ Ты не участник этой игры.", ephemeral=True)
            return

        is_p1 = interaction.user.id == p1.id

        if is_p1 and game["p1_choice"]:
            await interaction.response.send_message("⚠️ Ты уже сделал ход!", ephemeral=True)
            return
        if not is_p1 and game["p2_choice"]:
            await interaction.response.send_message("⚠️ Ты уже сделал ход!", ephemeral=True)
            return

        if is_p1:
            game["p1_choice"] = choice
        else:
            game["p2_choice"] = choice

        await interaction.response.send_message(
            f"✅ Ты выбрал {EMOJI[choice]} — ждём соперника!", ephemeral=True
        )

        p1_done = bool(game["p1_choice"])
        p2_done = bool(game["p2_choice"])

        if p1_done and p2_done:
            embed = build_result_embed(p1, p2, game["p1_choice"], game["p2_choice"])
            view = PlayAgainView(p1, p2)
            del active_games[self.game_id]
            await interaction.message.edit(embed=embed, view=view)
        else:
            embed = build_waiting_embed(p1, p2, p1_done, p2_done)
            await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="✊ Камень",   style=discord.ButtonStyle.primary)
    async def rock(self, interaction, button):
        await self.handle_choice(interaction, "rock")

    @discord.ui.button(label="✌️ Ножницы", style=discord.ButtonStyle.secondary)
    async def scissors(self, interaction, button):
        await self.handle_choice(interaction, "scissors")

    @discord.ui.button(label="🖐 Бумага",  style=discord.ButtonStyle.secondary)
    async def paper(self, interaction, button):
        await self.handle_choice(interaction, "paper")


class PlayAgainView(discord.ui.View):
    def __init__(self, p1: discord.User, p2: discord.User):
        super().__init__(timeout=300)
        self.p1 = p1
        self.p2 = p2

    @discord.ui.button(label="🔄 Сыграть снова", style=discord.ButtonStyle.success)
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in (self.p1.id, self.p2.id):
            await interaction.response.send_message("❌ Ты не участник этой игры.", ephemeral=True)
            return

        embed = build_waiting_embed(self.p1, self.p2, False, False)
        view = ChoiceView(game_id=0)

        await interaction.response.edit_message(embed=embed, view=view)
        msg = await interaction.original_response()

        view.game_id = msg.id
        active_games[msg.id] = {
            "p1": self.p1,
            "p2": self.p2,
            "p1_choice": "",
            "p2_choice": "",
        }


@bot.tree.command(name="кнб", description="Сыграть в камень-ножницы-бумагу с другим игроком")
@app_commands.describe(opponent="Игрок с которым хочешь сыграть")
async def knb(interaction: discord.Interaction, opponent: discord.User):
    if opponent.bot:
        await interaction.response.send_message("❌ Нельзя играть с ботом.", ephemeral=True)
        return
    if opponent.id == interaction.user.id:
        await interaction.response.send_message("❌ Нельзя играть с самим собой.", ephemeral=True)
        return

    p1 = interaction.user
    p2 = opponent

    embed = build_waiting_embed(p1, p2, False, False)
    view = ChoiceView(game_id=0)

    await interaction.response.send_message(embed=embed, view=view)
    msg = await interaction.original_response()

    view.game_id = msg.id
    active_games[msg.id] = {
        "p1": p1,
        "p2": p2,
        "p1_choice": "",
        "p2_choice": "",
    }


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Бот запущен как {bot.user}")


bot.run(TOKEN)
