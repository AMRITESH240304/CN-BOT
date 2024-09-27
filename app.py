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
            # Step 1: Check if the role is @everyone
            if role and role.is_default():  # is_default() returns True if it's @everyone
                await channel.send("@everyone")  # Send @everyone as a standalone message
            elif role:  # If a specific role is provided (not @everyone)
                await channel.send(role.mention)  # Send the role mention

            # Step 2: Create and send the embedded message
            embed = discord.Embed(
                title="📢 Announcement",
                description=message,  # Keep the original message
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )

            await channel.send(embed=embed)  # Send the embedded announcement

            # Acknowledge the interaction with an ephemeral message
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


@bot.tree.command(name='receive-list', description='Get the count of submissions and student names for a specific task')
async def receive_task(interaction: discord.Interaction, task_id: str):
    
    if not any(role.name in ['Head', 'Mods'] for role in interaction.user.roles):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    try:
        # Fetch the task with the given task ID
        task_ref = db.collection('tasks').document(task_id)
        task_snapshot = task_ref.get()

        # Check if the task exists
        if not task_snapshot.exists:
            await interaction.response.send_message(f"Task with ID {task_id} not found.", ephemeral=True)
            return

        # Get task details (name)
        task_data = task_snapshot.to_dict()
        task_name = task_data.get("task_name", "Unnamed Task")

        # Get the submissions from the 'receivers' subcollection
        receivers = task_ref.collection('receivers').stream()
        receiver_names = []
        count = 0

        for receiver in receivers:
            submission_data = receiver.to_dict()
            user_name = submission_data.get('user_name', 'Unknown User')
            receiver_names.append(user_name)
            count += 1

        # Create a column of student names (one name per line)
        student_names = "\n".join(receiver_names) if receiver_names else "No submissions yet."

        # Create the embed message
        embed = discord.Embed(
            title=f"Task: {task_name}",
            description=f"Task ID: {task_id}",
            color=discord.Color.orange()
        )

        # Add fields to embed
        embed.add_field(name="Submissions Count", value=f"{count} submissions", inline=False)
        embed.add_field(name="Students Who Submitted", value=student_names, inline=False)

        # Send the embed message
        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)



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
@bot.tree.command(name='help', description='Displays the list of available commands')
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot Commands",
        description="Here is a list of all available commands and their usage:",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="/create-task",
        value=(
            "**Description**: Create a new task.\n"
            "**Usage**: `/create-task task_name description due_date [link]`\n"
            "**Parameters**:\n"
            "- `task_name` (required): The name of the task.\n"
            "- `description` (required): A brief description of the task.\n"
            "- `due_date` (required): Task due date (format: YYYY-MM-DD).\n"
            "- `link` (optional): Optional link related to the task."
        ),
        inline=False
    )

    embed.add_field(
        name="/assign-task",
        value=(
            "**Description**: Assign a task to a specific role.\n"
            "**Usage**: `/assign-task task_id role`\n"
            "**Parameters**:\n"
            "- `task_id` (required): The ID of the task to be assigned.\n"
            "- `role` (required): The role to which the task will be assigned."
        ),
        inline=False
    )

    embed.add_field(
        name="/list-tasks",
        value=(
            "**Description**: List all tasks, optionally filtered by a role.\n"
            "**Usage**: `/list-tasks [role]`\n"
            "**Parameters**:\n"
            "- `role` (optional): Filter tasks assigned to a specific role. If omitted, all tasks are shown."
        ),
        inline=False
    )

    embed.add_field(
        name="/submit-task",
        value=(
            "**Description**: Submit a task you have completed.\n"
            "**Usage**: `/submit-task task_id link`\n"
            "**Parameters**:\n"
            "- `task_id` (required): The ID of the task you are submitting.\n"
            "- `link` (required): A link to the submission (e.g., a document or resource)."
        ),
        inline=False
    )

    embed.add_field(
        name="/complete-task",
        value=(
            "**Description**: Mark a task as completed.\n"
            "**Usage**: `/complete-task task_id`\n"
            "**Parameters**:\n"
            "- `task_id` (required): The ID of the task to be marked as completed."
        ),
        inline=False
    )

    embed.add_field(
        name="/delete-task",
        value=(
            "**Description**: Delete a task (restricted to 'Head' role).\n"
            "**Usage**: `/delete-task task_id`\n"
            "**Parameters**:\n"
            "- `task_id` (required): The ID of the task to be deleted."
        ),
        inline=False
    )

    embed.add_field(
        name="/announce",
        value=(
            "**Description**: Make an announcement in a specified channel.\n"
            "**Usage**: `/announce channel message [role]`\n"
            "**Parameters**:\n"
            "- `channel` (required): The text channel where the announcement will be made.\n"
            "- `message` (required): The announcement text.\n"
            "- `role` (optional): Mention a specific role or use `@everyone`."
        ),
        inline=False
    )

    embed.add_field(
        name="/receive",
        value=(
            "**Description**: Receive a task by individual members.\n"
            "**Usage**: `/receive role task_id`\n"
            "**Parameters**:\n"
            "- `role` (required): The role you belong to or are assigned to.\n"
            "- `task_id` (required): The ID of the task to receive."
        ),
        inline=False
    )

    embed.add_field(
        name="/view-submissions",
        value=(
            "**Description**: View all submitted tasks (restricted to 'Head' role).\n"
            "**Usage**: `/view-submissions`\n"
            "**Parameters**: None."
        ),
        inline=False
    )

    embed.add_field(
        name="/receive-list",
        value=(
            "**Description**: Get a count of submissions and the names of students for a specific task.\n"
            "**Usage**: `/receive-list task_id`\n"
            "**Parameters**:\n"
            "- `task_id` (required): The ID of the task to view the submissions for."
        ),
        inline=False
    )

    await interaction.response.send_message(embed=embed)



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
