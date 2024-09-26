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

cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.tree.command(name='create-task', description='Create a new task')
async def create_task(interaction: discord.Interaction, task_name: str, description: str, due_date: str, link: str = None):
    required_roles = ['Head', 'mods']  # Specify the role names allowed to create tasks
    if any(role.name in required_roles for role in interaction.user.roles):
        try:
            due_date_obj = datetime.strptime(due_date, "%Y-%m-%d")

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

    role_id = str(role.id) if role else None

    for task in tasks:
        task_data = task.to_dict()

        if role_id is None or task_data['assigned_role'] == role_id:
            due_date_str = task_data['due_date']

            due_date_obj = datetime.fromtimestamp(int(due_date_str))

            due_date_timestamp = int(due_date_obj.timestamp())

            assigned_role = interaction.guild.get_role(int(task_data['assigned_role'])) if task_data['assigned_role'] else None
            assigned_role_name = assigned_role.name if assigned_role else "None"

            embed_value = (
                f"**Name:** {task_data['task_name']}\n"
                f"**Description:** {task_data['description']}\n"
                f"**Due Date:** <t:{due_date_timestamp}:F>\n"  # Display as full date/time
                f"**Assigned Role:** {assigned_role_name}\n"
                f"**Status:** {task_data['status']}\n"
            )

            if task_data.get('link'):
                embed_value += f"**Link:** [Click Here]({task_data['link']})\n"

            embed.add_field(name=f"Task ID: {task.id}", value=embed_value, inline=False)
            task_found = True

    if not task_found:
        embed.description = "No tasks found." if role_id is None else f"No tasks found for role: {role.name}"

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='submit-task', description='Submit your task')
async def submit_task(interaction: discord.Interaction, task_id: str, link: str):
    await interaction.response.defer(ephemeral=True)

    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()

    if task.exists:
        receiver_ref = task_ref.collection('receivers').document(str(interaction.user.id))
        receiver = receiver_ref.get()

        if receiver.exists:
            receiver_data = receiver.to_dict()

            if receiver_data.get('status') == 'completed':
                await interaction.followup.send("You have already submitted this task.", ephemeral=True)
                return

            receiver_ref.update({
                'status': 'completed',
                'submission_link': link,
                'submitted_at': datetime.now().timestamp()
            })

            await interaction.followup.send(f"Task '{task.get('task_name')}' submitted successfully with the link: {link}")
        else:
            await interaction.followup.send("Please use /receive to receive the task first.", ephemeral=True)
    else:
        await interaction.followup.send(f"Task with ID {task_id} not found.", ephemeral=True)


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
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, message: str, role: discord.Role = None):
    required_roles = ['Head', 'mods']  # Specify the role names allowed to make announcements
    if any(role.name in required_roles for role in interaction.user.roles):
        try:
            embed = discord.Embed(
                title="📢 Announcement",
                description=message,
                color=discord.Color.orange(),  # You can change the color if you'd like
                timestamp=datetime.utcnow()  # Set the current time as timestamp
            )

            # Send the role mention first if provided
            mention_text = role.mention if role else ""
            await channel.send(content=mention_text, embed=embed)

            # Acknowledge the interaction with a message
            await interaction.response.send_message(f"Announcement sent to {channel.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to send messages in that channel.", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Failed to send the message. Please try again later.", ephemeral=True)
    else:
        await interaction.response.send_message("You do not have permission to make announcements.", ephemeral=True)


@bot.tree.command(name='receive', description='To receive the task by individual members')
async def task_receive(interaction: discord.Interaction, role: discord.Role, task_id: str):
    required_roles = ['Head', 'mods','Ninjas'] 
    user_name = interaction.user.display_name  

    await interaction.response.defer()

    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()

    if task.exists:
        task_data = task.to_dict()

        if role.name in required_roles or task_data['assigned_role'] == str(role.id):
            receivers_ref = task_ref.collection('receivers').document(str(interaction.user.id))  
            
            if not receivers_ref.get().exists:
                receivers_ref.set({
                    'user_name': user_name,
                    'status': 'pending',  
                    'received_at': datetime.now().timestamp()  
                })

                await interaction.followup.send(f"Task '{task_data['task_name']}' received by {user_name}.")
            else:
                await interaction.followup.send(f"You have already received the task '{task_data['task_name']}'.")
        else:
            await interaction.followup.send(f"You're not authorized to receive this task.")
    else:
        await interaction.followup.send(f"Task with ID '{task_id}' not found.")

@bot.tree.command(name='view-submissions', description='View all submitted tasks')
async def view_submissions(interaction: discord.Interaction):
    # Check if the user has the required 'Head' role
    if not any(role.name == 'Head' for role in interaction.user.roles):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    # Fetch all tasks
    tasks = db.collection('tasks').stream()
    embed = discord.Embed(title="Submitted Tasks", color=discord.Color.blue())

    task_found = False

    for task in tasks:
        task_data = task.to_dict()
        task_id = task.id
        task_name = task_data.get("task_name", "N/A")

        # Fetch submissions for each task
        submissions = task.reference.collection('receivers').where('status', '==', 'completed').stream()

        for submission in submissions:
            submission_data = submission.to_dict()
            username = submission_data.get('user_name', 'Unknown User')
            submission_link = submission_data.get('submission_link', 'No link provided')

            # Add submission details to embed
            embed.add_field(
                name=f"Task Name: {task_name} (ID: {task_id})",
                value=f"**Username:** {username}\n**Link:** [Submission Link]({submission_link})",
                inline=False
            )
            task_found = True

    if not task_found:
        embed.description = "No submitted tasks found."

    await interaction.response.send_message(embed=embed)


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
    if message.content.strip() == "/lund" or message.content.strip() == "/machuda":
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
        await message.delete(delay = 15)

    # Ensure other commands still work
    await bot.process_commands(message)
    
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user} and synced commands.")

# Start the bot
keep_alive()
bot.run(DISCORD_TOKEN)
