import discord
import praw
import os
import re
import datetime
from datetime import datetime
from discord.ext import tasks
from replit import db
from keep_alive import keep_alive

posts_to_fetch = 8
target_time_1 = "11:00" #11:00
target_time_2 = "23:00" #23:00

#------------
#   Reddit
#------------

reddit = praw.Reddit(
  client_id=os.environ['REDDIT_CID'], 
  client_secret=os.environ['REDDIT_SECRET'], 
  user_agent=os.environ['REDDIT_UAGENT']
)

def sort_posts(target_title_list, target_url_list): #Put free deals at the end
  free_title_list = []
  free_url_list = []
  nonfree_title_list = []
  nonfree_url_list = []
  
  for i in range(len(target_title_list)):
    x = re.findall('100%', target_title_list[i]) #Regex to find all 100% deals
    
    if x: #If: 100%, else: not 100%
      free_title_list.append(target_title_list[i])
      free_url_list.append(target_url_list[i])
    else:
      nonfree_title_list.append(target_title_list[i])
      nonfree_url_list.append(target_url_list[i])

  #Concatenate into final/definite lists
  title_list = nonfree_title_list + free_title_list
  url_list = nonfree_url_list + free_url_list

  return title_list, url_list

def get_hot_posts(): #fetch top n posts from hot section of given subreddit
  hot_posts = reddit.subreddit('GameDeals').hot(limit=posts_to_fetch)
  aux_title_list = []
  aux_url_list = []

  for post in hot_posts: #save titles and urls into lists and return them
    aux_title_list.append(post.title)
    aux_url_list.append(post.url)

  title_list, url_list = sort_posts(aux_title_list, aux_url_list)

  return title_list, url_list

#-------------
#   Discord
#-------------

prefix = '$'
frecuency = 12 #hours
client = discord.Client()

#### Embed functions ####

def build_deal_embed(title, url, color=discord.Color.blue()):
  x = re.findall('100%', title) #Use regex to check for 100% discount
  if x:
    color = discord.Color.red()

  embed = discord.Embed(
    title='Game Deal',
    description=title, 
    color=color
  )
  embed.add_field(name='Link:', value=url, inline=False)
  return embed

def build_help_embed(): #Assemble the embed with the bot info
  embed = discord.Embed(
    title='Hey, Scavenger here!',
    description='Here is some info about me:',
    color=discord.Color.gold()
  )
  embed.add_field(
    name='$start command',
    value='This command will initiate the automatic search process. Use it in the channels you want me to post in.',
    inline=False)
  embed.add_field(
    name='$stop command',
    value='This command will stop me from posting in a previously set channel.',
    inline= False
  )
  embed.add_field(
    name='$search command',
    value='This command will make me search for deals manually once.',
    inline=False
  )
  embed.add_field(
    name='Frecuency',
    value='I search and post in intervals of '+str(frecuency)+' hours.',
    inline=False
  )
  embed.add_field(
    name='Free games',
    value='Whenever I find a free game, I will make an embed with a RED stripe',
    inline=False
  )
  embed.set_footer(text='Bot made by Outfasted')

  return embed

#### Database management ####

def add_to_db(message):
  channel_list = db['channels']           #Fetch the list
  current_channel_id = message.channel.id #Get the current ids to add

  if current_channel_id in channel_list:  #add only if not already present
    return
  else: 
    channel_list.append(current_channel_id)
    db['channels'] = channel_list

def del_from_db(message):
  channel_list = db['channels']           #Fetch the list
  current_channel_id = message.channel.id #Get the current ids to delete

  if current_channel_id in channel_list:  #del only if already present
    channel_list.remove(current_channel_id)
    db['channels'] = channel_list
  else:
    return
  
#### Automatic executions ####

@client.event
async def on_ready():
  print('We have logged in as {0.user}'.format(client))
  await client.change_presence(activity=discord.Game(name='$help')) #Set status

  #Initialize db if it's empty
  try: db['channels'] 
  except: db['channels'] = []

  search_loop.start() #Must be here to allow cache to fill up first; avoids errors
  
@client.event
async def on_guild_join(guild): 

  #Intro message when bot joins a server
  for channel in guild.text_channels:
    if channel.permissions_for(guild.me).send_messages:
      await channel.send('Hello, my name is Scavenger! Use $help to see some info about me. Use $start to begin searching.')
    break

@tasks.loop(minutes=1) #automatic loop (checks every minute)
async def search_loop():
  current_time = datetime.now().strftime("%H:%M") #hour %H min %M sec %S am:pm %p 
  print(current_time)

  if current_time == target_time_1 or current_time == target_time_2: #is it time to post?
    print('Num of guilds: ' + str(len(client.guilds))) #Check num of guilds bot is in

    target = db['channels'] #fetch list of guilds to post in

    #fetch the game deals and store them in db
    title_list, url_list = get_hot_posts()
    db['titles'] = title_list
    db['urls'] = url_list

    for i in range(len(target)):  #Broadcast the self-cmd
      try:
        await client.get_channel(target[i]).send('Scavenging')
      except AttributeError: #If bot was kicked or server deleted
        pass

#### Commands ####

@client.event
async def on_message(message):

  #Auto cmd for posting
  if message.content.startswith('Scavenging') and message.author == client.user:
    title_list = db['titles']
    url_list = db['urls']

    for i in range(len(title_list)): #assemble the message embed
      await message.channel.send(embed=build_deal_embed(title_list[i], url_list[i]))
    return

  if message.content.startswith(prefix + 'dev'): #dev cmd to change status
    if message.author.id == int(os.environ['ID']):
      await client.change_presence(activity=discord.Game(name='UNDERGOING MAINTENANCE'))
    return

  if message.content.startswith(prefix + 'undev'): #dev cmd to restore status
    if message.author.id == int(os.environ['ID']):
      await client.change_presence(activity=discord.Game(name='$help'))
    return
  
  if message.author == client.user or message.author.bot: #Ignore if own msg or if bot
    return

  if message.content.startswith(prefix):
    if not message.author.guild_permissions.administrator: #Ignore if not admin
      await message.channel.send('Admin powers are required')
      return

  if message.content.startswith(prefix + 'search'): #Manual search
    title_list, url_list = get_hot_posts() #fetch posts from reddit

    for i in range(len(title_list)): #Assemble the message embed
      await message.channel.send(embed=build_deal_embed(title_list[i], url_list[i]))
    return

  if message.content.startswith(prefix + 'hello'):  #Test cmd
    await message.channel.send('Hello!')
    return

  if message.content.startswith(prefix + 'help'):   #Help embed cmd
    await message.channel.send(embed=build_help_embed())
    return

  if message.content.startswith(prefix + 'start'):  #Init automatic search cmd
    add_to_db(message)
    await message.channel.send('I will now post here!')
    return

  if message.content.startswith(prefix + 'stop'):   #Stop automatic search cmd
    del_from_db(message)
    await message.channel.send('I will no longer post here!')
    return

keep_alive()                    #Start web server
client.run(os.environ['TOKEN']) #Execute disc bot