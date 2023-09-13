import os
import sys
import imaplib
import email
import collections
import argparse



 



def menu() -> int:
	"""
	Main Program Menu
	"""
	res = 0
	print("*Instructions: Run Login  discovery before anything else*")
	print("[1] Login and run Sender discovery")
	print("[2] Run Inbox Sort (moves emails to labels by domain)")
	print("[3] Delete emails in certain folders/labels (You will select which emails to delete)")
	print("[4] exit")
	while int(res) not in range(1,5):
		res = input("Enter an option 1-4: ")
		if not res.isnumeric(): #validate input
			print("Enter valid option")
			res = 0
	return int(res) 

def getSenders(username: str, password: str) -> tuple:
	"""
	1.Login to gmail Account
	2. Create Counter to track number of emails sent from each domain
	3. also map Email UID to each domain
	4. return counter and map in tuple
	"""
	global imap #make global so it can be used by other functions 
	counter  = collections.Counter()
	uid_map = collections.defaultdict(list)


	imap = imaplib.IMAP4_SSL('imap.gmail.com') #open connection
	print("Logging into", username)
	imap.login(username, password) 
	imap.select('inbox') #selecting inbox 
	
	print("Getting Email UIDs")
	status, email_uids = imap.search(None, 'ALL')
	if status != 'OK':
		raise Exception("Error running imap search for gmail messages: "
        	"%s" % status)
	email_uids= email_uids[0].split() 
	fetch_ids = b','.join(email_uids) #creating set of iuds to do one fetch instead of many

	print("Fetching email sender info from header")
	status, email_data = imap.fetch(fetch_ids, '(BODY.PEEK[HEADER.FIELDS (FROM)])')
	if status != 'OK':
		raise Exception("Error running imap fetch for senders: "
        	"%s" % status)
	print("proccessing sender email info")
	for i in range(len(email_data)):
		if i % 2 != 0:
			continue
		uid_val = email_data[i][0].split()[0] #get email uid for map
		email_from = str(email_data[i][-1]).split('<')[-1].split('>')[0] #get email 
		if '\\' in email_from: #handle potential extra bytes present in some emails
			email_from = email_from.split("\\")[0]
		domain = email_from.split('@')[-1].split('.') #split email into two strings at the '@' then take the  string after the @ and split it at the '.'
		counter[(domain[-2] + '.' +domain[-1]).lower()] += 1 #increase counter for domain
		uid_map[(domain[-2] + '.' +domain[-1]).lower()].append(uid_val)  #save uid for email in map using domain as key
	print("Sender emails processed!")
	return (counter, uid_map)

def setIgnoreList(count: dict) -> tuple:
	"""
	Set up what emails to ignore based of cut off value and user entered ignorelist
	:param counter: count of domains 
	"""
	ignoreList,big,smol, cutoff = set(),max(count.values()),min(count.values()), None


	print("The domain that has sent you the most emails has sent ",big, " emails")
	print("The domain that has sent you the least emails has sent ",smol, " emails")
	print("We are gonna be moving emails into folders based off domain.")
	print("Enter a cut off number. (any domain with less than this number will not be moved into a unique folder)")
	while not cutoff or cutoff > big or cutoff < smol:
		cutoff = input("Enter a number: ")
		cutoff = int(cutoff) if cutoff.isnumeric() else None
		if type(cutoff) != int:
			print("Enter a valid int")
		elif cutoff >= big:
			print("Enter a number smaller than ", big)
		elif cutoff < smol:
			print("Enter a number bigger than ", smol)
	
	res = None

	print("There maybe specific domains you want to ignore such as gmail.com, yahoo.com...etc")
	print("Lets set some of those to ignore")
	while res not in ('y','n'):
		res = input("First, would you like to view a list of the domains?(y/n)").lower()
		if res not in ('y','n'):
			print("Input was invalid")
	if res == 'y':
		templist = sorted(list(count.keys()), key = lambda x: -count[x])
		for a,b,c in zip(templist[::3], templist[1::3], templist[2::3]):
			if count[a] < cutoff: break
			print(f'{a+":"+str(count[a]): <40}{b +":"+str(count[b]): <40}{c+":"+str(count[c])}')

	res = None
	while True:
		res = input("Enter domain to ignore, when done enter 'done': ").lower()
		if res == 'done':
			break
		elif res not in count:
			print("domain entered not is not in the list")
		else:
			print("Adding", res, "to ignore list")
			ignoreList.add(res)
	print("Saving cutoff value and ignore list")
	return (cutoff, ignoreList)

def SortEmails(count: dict, uid_map: dict, cutoff: int, ignoreList: set):
	"""
	1. Gets current label/folder structure from inbox
	2. Moves emails into label by either creating new label when needed or adding emails to existing label

	:param count: counter of emails domains 
	:param uid_map: hash table containing uid of emails with key being domain
	:param cutoff: int value representing min value of emails needed to create new label 
	:param ignoreList: set of domains to ignore when creating labels
	"""
	domainList = sorted(list(count.keys()), key = lambda x: -count[x]) #gets list of domain sorted by email count desc
	
	print("getting label/folder info")
	res,folder_data = imap.list()
	folders = set([folder.split()[-1].decode("utf-8").strip('\"') for folder in folder_data]) 

	print("Moving emails into labels")
	for domain in domainList:
		if domain in ignoreList or count[domain] < cutoff: #ignore domains on ignoreList or with less emails than cutoff value
			continue
		else:
			if domain not in folders: #check if folder/label exists and create it if it does not exist
				print("Creating label for", domain, "and adding it to", count[domain], "emails ")
				imap.create(domain)
			else:
				print("label exists for", domain, "now adding", count[domain], "emails to label")
			domain_uids = b','.join(uid_map[domain]) #create one list of UIDs in label to speed up addition of label
			imap.store(domain_uids, '+X-GM-LABELS', '('+domain+')') #add label to all emails of domain
	print("done")
	return

def deleteEmails(username: str, password: str):
	"""
	1. Gets Folder/Label structure of inbox
	2. Lets users pick which folders/labels to delete
	3. deletes selected folders/label
	"""
	print("Getting folder info from", username)
	res,folder_data = imap.list()
	folders = list([folder.split()[-1].decode("utf-8").strip('\"') for folder in folder_data]) 
	count = 0
	confirm = 'w'
	for a,b,c in zip(folders[::3], folders[1::3], folders[2::3]):
		print(f'{"["+str(count)+"] "+ a: <40}{"["+str(count+1)+"] "+b: <40}{"["+str(count+2)+"] "+c}')
		count += 3
	print("Enter folders to delete (also deleting emails inside folders) from list by inputting numbers seperated by commas:")
	selected = input()
	selected = [int(x) for x in selected.replace(" ","").split(',')]
	while confirm.lower() != 'y':
		count = 0
		print("These are the folders you want to delete:")
		for a,b,c in zip(selected[::3], selected[1::3], selected[2::3]):
			print(f'{str(count)+". "+folders[a]: <40}{str(count+1)+". "+folders[b]: <40}{str(count+2)+". "+folders[c]: <40}')
			count += 3
		confirm = input("Confirm(y/n)?: ")
		if confirm.lower() == 'n':
			print("Enter numbers to remove(seperated by commas): ")
			remove = input()
			for num in remove.replace(" ","").split(","):
				selected.pop(int(num))
	for num in selected:
		curr = imap.select(folders[num])
		print("Moving emails in",folders[num], "to trash and deleting label")
		imap.store("1:*",'+X-GM-LABELS', '\\Trash') # move emails to trash
		imap.delete(folders[num]) #delete folder
	print("Nothing has been permanently deleted but instead moved to trash")
	print("Done!")
	return

def main():
	parser = argparse.ArgumentParser(description="Parse login credentials (username/app password)")
	parser.add_argument("--username",
					 action="store",
					 help="Enter email to use",
					 dest="username",
					 required=True)
	parser.add_argument("--password",
					 action="store",
					 help="Enter App password to login",
					 dest="password",
					 required=True)
	parsed_args = parser.parse_args(sys.argv[1:])

	username, password = parsed_args.username, parsed_args.password
	res = None 
	login = False

	while res != 4:
		res = menu()
		if res == 1:
			count, uid_map = getSenders(username,password)
			login = True
		elif res == 2:
			if not login:
				print("Need to run login and discovery before this")
				continue
			cutoff, ignoreList = setIgnoreList(count)
			folders = SortEmails(count,uid_map,cutoff,ignoreList)
		elif res == 3:
			if not login:
				print("Need to run login and discovery before this")
				continue
			deleteEmails(username, password)
		else:
			print("Goodbye!")
			return 
    

if __name__ == "__main__":
    main()
