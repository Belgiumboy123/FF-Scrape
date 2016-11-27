from itertools import chain
from bs4 import BeautifulSoup
import csv
from time import sleep
import sys
import os

'''
Fantasy Team Name
Player Name
Player Team
Player Position
Amount

'''

def LoadDraft():
	rows = []

	html = open("draft/draft.html", "r").read()
	soup = BeautifulSoup(html, 'html.parser')

	
	for team in soup.find_all('tr', class_='tableHead'):
		
		for player in team.find_next_siblings('tr'):

			rowData = []
			
			#Need to grab the owner name because
			#We have one too many 'Butt Stuffs' in our league
			title = team.a['title']
			idxStart = title.index('(')
			idxEnd = title.index(')')
			owner = title[idxStart+1:idxEnd]
			rowData.append(owner)

			data = player.find_all('td')
			playerName = data[1].a.text.strip()
			rowData.append(playerName)
			playerData = data[1].text.strip()
			if 'D/ST' in playerData:
				rowData.append("") # defensive team name.
				rowData.append("Defense")
			else:
				playerDetails = playerData.split(',')[1].strip().split()
				rowData.append(playerDetails[0])
				rowData.append(playerDetails[1])

			rowData.append(data[2].text.strip()[1:])

			rows.append(rowData)


	with open("draft.csv", "w") as f:
		writer = csv.writer(f)
		writer.writerows(rows)

#
# ScoreRowData
#    Week
#    Owner name
#    TeamName
#    Fantasy Opp
#    Slot
#	 Player Name
#    Team
#    Pos
#    player - Opp
#    Pts
#    Fantasy Week

def LoadStatsForPage(htmlFile, rows):

	html = open(htmlFile, "r").read()
	soup = BeautifulSoup(html, 'html.parser')
  
  	# get week
  	week = soup.find('div', class_='games-pageheader').em.text[5:].strip()

	players = soup.find_all('table', class_='playerTableTable tableBody')

	teamNames = []
	for player in players:
		teamName = player.find('tr', class_='playerTableBgRowHead').td.text[:-9].strip().upper()
		teamNames.append(teamName)

	owners = []
	ownerNames = soup.find_all('div', class_='teamInfoOwnerData')
	for owner in ownerNames:
		x = owner.encode('utf-8')
		idx =  len('<div class="teamInfoOwnerData">')
		idx2 = x.index("</div>")
		owner = x[idx:idx2]
		owners.append(owner)

	for index,playerTable in enumerate(players):

		playerRows = playerTable.find_all('tr', class_='pncPlayerRow')
		
		for row in playerRows:
			rowData = []
			rowData.append(week)
			rowData.append(owners[index])
			rowData.append(teamNames[index])
			rowData.append(teamNames[(index+1)%2])

			isDefense = False
			slot = row.find('td', class_='playerSlot').text.strip()
			if slot == 'RB/WR':
				slot = 'FLEX'
			elif slot == 'D/ST':
				slot = 'DEF'
				isDefense = True
			elif slot == 'FLEX':
				slot = 'EX-FLEX'

			rowData.append(slot)

			playerInfo = row.find('td', class_='playertablePlayerName')

			# Some terrible human forgot to start anyone at all
			if playerInfo is None:
				rows.append(rowData)
				continue

			playerName = playerInfo.a.text.strip()
			rowData.append(playerName)

			if isDefense:
				rowData.append("")  #TODO get team name and convert to 3 letter shorthand
				rowData.append("Defense")
			else:
				playerInfoString = playerInfo.text.strip()
				details = playerInfoString.split(",")[1].strip().split()
				rowData.append(details[0])
				rowData.append(details[1])

			rowData.append(row.find('td', class_='').text)
			rowData.append(row.find('td', class_='playertableStat').text)

			rows.append(rowData)


def LoadStats():

	rows = []

	dirname = 'boxscores'
	for item in os.listdir(dirname):
		print(item)
		LoadStatsForPage( dirname + '/'+item, rows)

	with open("boxscoredata.csv", "w") as f:
		writer = csv.writer(f)
		writer.writerows(rows)		
 


def main():
	#LoadStats()
	LoadDraft()  
	
                             
if __name__ == '__main__':
    main()