import discord
from discord.ext import commands
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv
from keep_alive import keep_alive
from datetime import datetime


# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH")

# Firebase setup
cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Command to create a new task (restricted to users with the 'Head' role)
@bot.tree.command(name='create-task', description='Create a new task')
async def create_task(interaction: discord.Interaction, task_name: str, description: str, due_date: str, link: str = None):
    required_roles = ['Head', 'mods']  # Specify the role names allowed to create tasks
    if any(role.name in required_roles for role in interaction.user.roles):
        try:
            # Convert the due date from string to datetime object
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d")

            # Convert the datetime object to a Unix timestamp
            due_date_timestamp = str(int(due_date_obj.timestamp()))
        except ValueError:
            await interaction.response.send_message("Invalid date format. Please use YYYY-MM-DD", ephemeral=True)
            return

        task_ref = db.collection('tasks').document()
        task = {
            "task_name": task_name,
            "description": description,
            "due_date": due_date_timestamp,  # Store as Unix timestamp
            "assigned_role": None,
            "status": "pending",
            "link": link  # Store the link if provided
        }
        task_ref.set(task)
        await interaction.response.send_message(f"Task '{task_name}' created with ID: {task_ref.id}")
    else:
        await interaction.response.send_message("You do not have permission to create tasks.", ephemeral=True)

# Command to assign task to a role
@bot.tree.command(name='assign-task', description='Assign a task to a role')
async def assign_task(interaction: discord.Interaction, task_id: str, role: discord.Role):
    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()
    if task.exists:
        task_ref.update({"assigned_role": str(role.id)})
        await interaction.response.send_message(f"Task '{task.get('task_name')}' assigned to role '{role.name}'")
    else:
        await interaction.response.send_message(f"Task with ID {task_id} not found.")

# Command to list all tasks
@bot.tree.command(name='list-tasks', description='List tasks optionally filtered by assigned role')
async def list_tasks(interaction: discord.Interaction, role: discord.Role = None):
    tasks = db.collection('tasks').stream()
    embed = discord.Embed(title="Tasks List", color=discord.Color.orange(), description="Here are your tasks:")

    task_found = False

    # Extract the role ID if a role mention is provided
    role_id = str(role.id) if role else None

    for task in tasks:
        task_data = task.to_dict()

        # If role is provided, filter tasks by assigned_role, otherwise list all tasks
        if role_id is None or task_data['assigned_role'] == role_id:
            # Get the due date directly (it is a Unix timestamp stored as a string)
            due_date_str = task_data['due_date']

            # Convert the due date from Unix timestamp to datetime object
            due_date_obj = datetime.fromtimestamp(int(due_date_str))

            # Convert the datetime object to a Unix timestamp for embed display
            due_date_timestamp = int(due_date_obj.timestamp())

            # Retrieve the role object using the assigned_role ID
            assigned_role = interaction.guild.get_role(int(task_data['assigned_role'])) if task_data['assigned_role'] else None
            assigned_role_name = assigned_role.name if assigned_role else "None"

            embed_value = (
                f"**Name:** {task_data['task_name']}\n"
                f"**Description:** {task_data['description']}\n"
                f"**Due Date:** <t:{due_date_timestamp}:F>\n"  # Display as full date/time
                f"**Assigned Role:** {assigned_role_name}\n"
                f"**Status:** {task_data['status']}\n"
            )

            # Add the link if it exists
            if task_data.get('link'):
                embed_value += f"**Link:** [Click Here]({task_data['link']})\n"

            embed.add_field(name=f"Task ID: {task.id}", value=embed_value, inline=False)
            task_found = True

    if not task_found:
        embed.description = "No tasks found." if role_id is None else f"No tasks found for role: {role.name}"

    await interaction.response.send_message(embed=embed)


# Command to mark a task as completed
@bot.tree.command(name='complete-task', description='Mark a task as completed')
async def complete_task(interaction: discord.Interaction, task_id: str):
    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()
    if task.exists:
        task_ref.update({"status": "completed"})
        await interaction.response.send_message(f"Task '{task.get('task_name')}' marked as completed.")
    else:
        await interaction.response.send_message(f"Task with ID {task_id} not found.")

# Command to delete a task (restricted to users with the 'Head' role)
@bot.tree.command(name='delete-task', description='Delete a task')
async def delete_task(interaction: discord.Interaction, task_id: str):
    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()
    if task.exists:
        task_ref.delete()
        await interaction.response.send_message(f"Task with ID {task_id} deleted.")
    else:
        await interaction.response.send_message(f"Task with ID {task_id} not found.")

@bot.tree.command(name='announce', description='Make an announcement in a specified channel')
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    required_roles = ['Head', 'mods']  # Specify the role names allowed to make announcements
    if any(role.name in required_roles for role in interaction.user.roles):
        try:
            # Create an embed with the announcement message
            embed = discord.Embed(
                title="📢 Announcement",
                description=message,
                color=discord.Color.orange(),  # You can change the color if you'd like
                timestamp=datetime.utcnow()  # Set the current time as timestamp
            )

            # Send the embed to the specified channel
            await channel.send(embed=embed)
            await interaction.response.send_message(f"Announcement sent to {channel.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to send messages in that channel.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Failed to send the message. Please try again later.", ephemeral=True)
    else:
        await interaction.response.send_message("You do not have permission to make announcements.", ephemeral=True)

# Command to update task description or due date
# @bot.tree.command(name='update-task', description='Update task description or due date')
# async def update_task(interaction: discord.Interaction, task_id: str, new_description: str, new_due_date: str):
#     task_ref = db.collection('tasks').document(task_id)
#     task = task_ref.get()
#     if task.exists:
#         updates = {}
#         if new_description:
#             updates["description"] = new_description
#             await task_ref.update({"description": new_description})
#         if new_due_date:
#             updates["due_date"] = new_due_date
#             await task_ref.update({"due_date": new_due_date})
#         if updates:
#             await interaction.response.send_message(f"Task '{task.get('task_name')}' updated.")
#         else:
#             await interaction.response.send_message("No updates provided.")
#     else:
#         await interaction.response.send_message(f"Task with ID {task_id} not found.")

# Register commands with the Discord server
# Event listener to handle a hidden command
@bot.event
async def on_message(message):
    # Ignore messages sent by the bot itself
    if message.author == bot.user:
        return

    # Check if the message starts with /lund
    if message.content.strip() == "/lund":
        # Send the response and delete it after 15 seconds
        await message.channel.send(
            "yaha se lund phek ke maarunga pura parivar chud jayega pata bhi nhi chalega",
            delete_after=15
        )
        # Delete the original /lund command message
        await message.delete()

    # Check if the message starts with /machuda
    if message.content.strip() == "/machuda":
        # Send the response and delete it after 15 seconds
        await message.channel.send(
            "bhej teri maa ko",
            delete_after=15
        )
        # Delete the original /machuda command message
        await message.delete()

    # Ensure other commands still work
    await bot.process_commands(message)
    
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} and synced commands.")

# Start the bot
keep_alive()
bot.run(DISCORD_TOKEN)
