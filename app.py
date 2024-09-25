import discord
from discord.ext import commands
import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

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

# Task structure: {task_name, description, due_date, assigned_role, status}

# Command to create a new task
@bot.command(name='create-task')
async def create_task(ctx, task_name, description, due_date):
    task_ref = db.collection('tasks').document()
    task = {
        "task_name": task_name,
        "description": description,
        "due_date": due_date,
        "assigned_role": None,
        "status": "pending"
    }
    task_ref.set(task)
    await ctx.send(f"Task '{task_name}' created with ID: {task_ref.id}")

# Command to assign task to a role
@bot.command(name='assign-task')
async def assign_task(ctx, task_id: str, role: discord.Role):
    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()
    if task.exists:
        task_ref.update({"assigned_role": str(role.id)})
        await ctx.send(f"Task '{task.get('task_name')}' assigned to role '{role.name}'")
    else:
        await ctx.send(f"Task with ID {task_id} not found.")

# Command to list all tasks
@bot.command(name='list-tasks')
async def list_tasks(ctx):
    tasks = db.collection('tasks').stream()
    message = "Tasks:\n"
    for task in tasks:
        task_data = task.to_dict()
        message += f"ID: {task.id}, Name: {task_data['task_name']}, Status: {task_data['status']}\n"
    if message == "Tasks:\n":
        await ctx.send("No tasks found.")
    else:
        await ctx.send(message)

# Command to mark a task as completed
@bot.command(name='complete-task')
async def complete_task(ctx, task_id: str):
    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()
    if task.exists:
        task_ref.update({"status": "completed"})
        await ctx.send(f"Task '{task.get('task_name')}' marked as completed.")
    else:
        await ctx.send(f"Task with ID {task_id} not found.")

# Command to delete a task
@bot.command(name='delete-task')
async def delete_task(ctx, task_id: str):
    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()
    if task.exists:
        task_ref.delete()
        await ctx.send(f"Task with ID {task_id} deleted.")
    else:
        await ctx.send(f"Task with ID {task_id} not found.")

# Command to update task description or due date
@bot.command(name='update-task')
async def update_task(ctx, task_id: str, new_description=None, new_due_date=None):
    task_ref = db.collection('tasks').document(task_id)
    task = task_ref.get()
    if task.exists:
        updates = {}
        if new_description:
            updates["description"] = new_description
        if new_due_date:
            updates["due_date"] = new_due_date
        if updates:
            task_ref.update(updates)
            await ctx.send(f"Task '{task.get('task_name')}' updated.")
        else:
            await ctx.send("No updates provided.")
    else:
        await ctx.send(f"Task with ID {task_id} not found.")

# Start the bot
bot.run(DISCORD_TOKEN)
